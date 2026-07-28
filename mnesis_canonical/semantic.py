"""Dual-endpoint semantic perception — ObservationLabel / scene_graph / PS messages (C12).

The robot end (Mnesis-Daedalus) and the headset end (Mnesis-Eidolon) both look at
the same room and both produce *the same kind of thing*: "there is a ``cup`` at
this pose in the map, and I am 0.87 sure". This module is that one kind of thing,
defined once, in canonical — so the fuser does not open with an adapter layer and
``class_id`` does not drift between the two ends on day one.

Three layers, deliberately separate:

``ObservationLabel``
    One end's observation. Produced by robot, headset, or a human adjudication.
    Never authoritative on its own.

``scene_graph``
    The **fusion product**, authoritative, produced on the robot end only
    (Daedalus, ADR-004). A scene-graph label is an ``ObservationLabel`` plus the
    fusion verdict: ``state`` / ``witnesses`` / ``dispute``.

PS messages (8442 WS, envelope v1)
    ``semantic_label`` (up, event-driven) · ``scene_graph`` (down, 1–5 Hz,
    change-driven) · ``colocalization`` (bidirectional, low-frequency + event).
    Same public header as C3 — ``{type, seq, ts, body}`` — because they share the
    8442 socket with 30 Hz teleop frames.

This module defines and validates the contract; it does **not** fuse. Fusion is
Daedalus (ADR-004), headset-side consumption is Eidolon. See SPEC.md
§Dual-endpoint semantic perception and CONTRACTS.md C12.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import TypeGuard

from .taxonomy_registry import list_term_ids

_SCHEMA_PATH = Path(__file__).resolve().parent / "semantic.schema.json"

# --- Value domains -----------------------------------------------------------

#: Taxonomy backing ``ObservationLabel.class_id``.  The value domain lives in
#: ``taxonomies/object_class_v1.json`` and NOWHERE else: a consumer that needs a
#: class this taxonomy lacks opens a PR here rather than inventing a string,
#: otherwise the two ends stop meaning the same thing by the same word.
OBJECT_CLASS_TAXONOMY = "object_class_v1"

#: Who produced a label.  ``headset`` and ``human`` are in the enum **from day
#: one** even though headset-side recognition (PS4) and human adjudication are
#: backlog: adding an enum value later is a contract change, and every consumer
#: that hard-coded a two-value switch would have to be revisited.
LABEL_SOURCES = ("robot", "headset", "human")

#: Sources allowed on the **uplink** ``semantic_label`` message (headset → bridge).
#: A ``robot`` label never travels up — it is already on the authoritative side.
UPLINK_LABEL_SOURCES = ("headset", "human")

#: Fusion verdict carried by a scene-graph label.
#:   confirmed   — corroborated; ``witnesses`` says by whom.
#:   unconfirmed — a single witness so far, not contradicted.
#:   disputed    — witnesses disagree on the class; ``dispute`` records who said what.
#:   stale       — not re-observed recently; still believed to exist. A stale label
#:                 is NOT removed from the graph: "I no longer see it" and "it is
#:                 gone" are different claims, and only the producer can tell them
#:                 apart. Consumers render it degraded, they do not drop it.
LABEL_STATES = ("confirmed", "unconfirmed", "disputed", "stale")

#: Accepted ``frame_id`` values.  A label is a claim about a **shared** world, so
#: it must arrive in the common frame; a sensor- or headset-local pose is not
#: fusable and is rejected rather than silently mis-fused. Producers transform
#: into ``map`` first — the headset end using the ``colocalization`` extrinsic.
LABEL_FRAME_IDS = ("map",)

#: Colocalization tracking state.
#:   ok    — a currently valid ``T_map_headset``.
#:   stale — the last extrinsic is still carried but is no longer trusted.
#:   lost  — no usable extrinsic; the key is OMITTED (never identity, never zeros).
COLOCALIZATION_STATES = ("ok", "stale", "lost")

#: The event name carried by a ``colocalization`` message announcing loss of
#: alignment.  It is not a fourth message type: the event IS a ``colocalization``
#: message with a non-``ok`` state, so a consumer has one place to read alignment
#: health from.
COLOCALIZATION_STALE_EVENT = "colocalization_stale"

# --- 8442 envelope v1 --------------------------------------------------------

#: The three PS message types, on the C3 envelope (``{type, seq, ts, body}``).
PS_MESSAGE_TYPES = ("semantic_label", "scene_graph", "colocalization")

ENVELOPE_KEYS = ("type", "seq", "ts", "body")

_UINT32_MAX = 2**32 - 1

#: Teleop control frames own the 8442 socket at this rate; everything below is
#: sized so semantics never competes with them for bandwidth.
TELEOP_FRAME_HZ = 30.0

#: Sustained rate band for ``scene_graph``: change-driven, so silence is legal
#: when the map does not change — this is a **ceiling with a nominal floor**, not
#: a heartbeat. Do not implement a 1 Hz keep-alive off it.
SCENE_GRAPH_RATE_HZ = (1.0, 5.0)

SCENE_GRAPH_MAX_HZ = SCENE_GRAPH_RATE_HZ[1]
SEMANTIC_LABEL_MAX_HZ = 5.0
COLOCALIZATION_MAX_HZ = 1.0

#: Hard per-type sustained-rate ceilings (Hz).  Low frequency is a **requirement**,
#: not a guideline: these messages share the socket with 30 Hz teleop.  A producer
#: with several labels to send batches them into one ``semantic_label`` (the body
#: carries an array) instead of bursting.
PS_MAX_HZ = {
    "semantic_label": SEMANTIC_LABEL_MAX_HZ,
    "scene_graph": SCENE_GRAPH_MAX_HZ,
    "colocalization": COLOCALIZATION_MAX_HZ,
}

#: Tolerance on ``|q| == 1`` for a pose quaternion.
QUAT_NORM_TOLERANCE = 1e-3


@lru_cache(maxsize=1)
def object_class_ids() -> tuple[str, ...]:
    """Return the ``class_id`` value domain, read from the taxonomy registry.

    Cached: every label — and every ``dispute`` entry — is checked against it, so
    a scene graph would otherwise re-read the taxonomy file once per object.
    """
    return list_term_ids(OBJECT_CLASS_TAXONOMY)


def load_semantic_schema() -> dict:
    """Load the bundled PS message JSON Schema (Draft 2020-12) as a dict.

    Same contract as the pure-Python validators below; it exists so the headset
    end (JavaScript) can validate against the standard without a Python
    dependency — the consumers of C12 are two different language stacks.
    """
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def validate_ps_message_jsonschema(msg: dict) -> list[str]:
    """Validate one PS message against the bundled JSON Schema.

    Requires the optional ``jsonschema`` dependency (``pip install
    mnesis-canonical[jsonschema]``). Structure/types only — the cross-field rules
    that JSON Schema cannot express (unit quaternions, duplicate ``label_id``,
    witnesses ⊇ dispute keys, rate ceilings) live in :func:`validate_ps_message`
    and :func:`validate_ps_stream`.
    """
    try:
        import jsonschema
    except ImportError as e:  # pragma: no cover - exercised only without extra
        raise RuntimeError(
            "validate_ps_message_jsonschema requires the optional 'jsonschema' "
            "dependency; install with: pip install mnesis-canonical[jsonschema]"
        ) from e
    validator = jsonschema.Draft202012Validator(load_semantic_schema())
    return [err.message for err in sorted(validator.iter_errors(msg), key=str)]


# --- helpers -----------------------------------------------------------------


def _is_number(v: object) -> TypeGuard[int | float]:
    """True for real numbers; ``TypeGuard`` so callers' comparisons type-check."""
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_finite_number(v: object) -> TypeGuard[int | float]:
    return _is_number(v) and math.isfinite(float(v))


def _is_int(v: object) -> TypeGuard[int]:
    return isinstance(v, int) and not isinstance(v, bool)


def _check_str(obj: dict, key: str, path: str, errors: list[str]) -> None:
    val = obj.get(key)
    if not isinstance(val, str) or not val:
        errors.append(f"{path}.{key} must be a non-empty string, got {val!r}")


def _check_ns(obj: dict, key: str, path: str, errors: list[str]) -> None:
    val = obj.get(key)
    if not _is_int(val) or val < 0:
        errors.append(
            f"{path}.{key} must be a non-negative int (Unix nanoseconds), got {val!r}"
        )


def _check_vector(
    obj: dict, key: str, length: int, path: str, errors: list[str],
) -> list[float] | None:
    val = obj.get(key)
    if not isinstance(val, list) or len(val) != length:
        errors.append(f"{path}.{key} must be a list of {length} numbers, got {val!r}")
        return None
    if not all(_is_finite_number(x) for x in val):
        errors.append(f"{path}.{key} must contain only finite numbers, got {val!r}")
        return None
    return [float(x) for x in val]


def _validate_pose(pose: object, path: str, errors: list[str]) -> None:
    """Validate ``{"t": [x,y,z], "q": [x,y,z,w]}`` — metres + quaternion {x,y,z,w}.

    Quaternion order is scalar-last and the frame is right-handed, identical to
    every other pose in the standard (``head_pose_SE3``, C3 ``eef_pose``); a
    second convention inside one standard is how sign errors get shipped.
    """
    if not isinstance(pose, dict):
        errors.append(f"{path} must be an object with 't' and 'q', got {pose!r}")
        return
    _check_vector(pose, "t", 3, path, errors)
    q = _check_vector(pose, "q", 4, path, errors)
    if q is not None:
        norm = math.sqrt(sum(x * x for x in q))
        if abs(norm - 1.0) > QUAT_NORM_TOLERANCE:
            errors.append(
                f"{path}.q must be a unit quaternion {{x,y,z,w}} "
                f"(|q| = 1 ± {QUAT_NORM_TOLERANCE}), got |q| = {norm:.6f}"
            )


# --- ObservationLabel --------------------------------------------------------


def validate_observation_label(
    label: object,
    *,
    path: str = "label",
    allowed_sources: tuple[str, ...] = LABEL_SOURCES,
) -> list[str]:
    """Return a list of errors for one ``ObservationLabel`` (empty = valid).

    Args:
        label: The label dict.
        path: Prefix used in error messages (e.g. ``"body.labels[0]"``).
        allowed_sources: Narrowed ``source`` domain — the uplink
            ``semantic_label`` message passes :data:`UPLINK_LABEL_SOURCES`.
    """
    errors: list[str] = []
    if not isinstance(label, dict):
        errors.append(f"{path} must be a JSON object, got {type(label).__name__}")
        return errors

    _check_str(label, "label_id", path, errors)

    class_id = label.get("class_id")
    classes = object_class_ids()
    if class_id not in classes:
        errors.append(
            f"{path}.class_id must be an id from taxonomies/{OBJECT_CLASS_TAXONOMY}.json, "
            f"got {class_id!r} (consumers MUST NOT invent classes — add one there)"
        )

    conf = label.get("confidence")
    if not _is_finite_number(conf):
        errors.append(f"{path}.confidence must be a finite number in [0, 1], got {conf!r}")
    elif conf < 0.0 or conf > 1.0:
        errors.append(f"{path}.confidence must be in [0, 1], got {conf}")

    source = label.get("source")
    if source not in allowed_sources:
        errors.append(f"{path}.source must be one of {allowed_sources}, got {source!r}")

    if "sensor" in label:
        _check_str(label, "sensor", path, errors)

    frame_id = label.get("frame_id")
    if frame_id not in LABEL_FRAME_IDS:
        errors.append(
            f"{path}.frame_id must be one of {LABEL_FRAME_IDS}, got {frame_id!r} — "
            f"a label in a sensor- or headset-local frame is not fusable; "
            f"transform into the shared frame before publishing"
        )

    if "pose" not in label:
        errors.append(f"{path}.pose is required")
    else:
        _validate_pose(label["pose"], f"{path}.pose", errors)

    # extent: absent = unknown size (SPEC §Conventions iron rule "absent means
    # unknown"). Never null, never a zero vector — a 0-sized box is a claim.
    if "extent" in label:
        extent = _check_vector(label, "extent", 3, path, errors)
        if extent is not None and any(x <= 0.0 for x in extent):
            errors.append(
                f"{path}.extent must contain positive sizes in metres, got {extent!r} "
                f"(omit the key when the size is unknown)"
            )

    _check_ns(label, "observed_at_ns", path, errors)

    return errors


# --- scene_graph -------------------------------------------------------------


def _validate_scene_graph_label(label: object, path: str, errors: list[str]) -> None:
    """An ObservationLabel plus the fusion verdict (state / witnesses / dispute)."""
    errors.extend(validate_observation_label(label, path=path))
    if not isinstance(label, dict):
        return

    state = label.get("state")
    if state not in LABEL_STATES:
        errors.append(f"{path}.state must be one of {LABEL_STATES}, got {state!r}")

    witnesses = label.get("witnesses")
    if not isinstance(witnesses, list) or not witnesses:
        errors.append(
            f"{path}.witnesses must be a non-empty array of {LABEL_SOURCES}, "
            f"got {witnesses!r}"
        )
        witnesses = []
    else:
        unknown = [w for w in witnesses if w not in LABEL_SOURCES]
        if unknown:
            errors.append(
                f"{path}.witnesses must be a subset of {LABEL_SOURCES}, "
                f"got unknown {unknown!r}"
            )
        if len(set(witnesses)) != len(witnesses):
            errors.append(f"{path}.witnesses must not repeat a source, got {witnesses!r}")
        src = label.get("source")
        if src in LABEL_SOURCES and src not in witnesses:
            errors.append(
                f"{path}.witnesses must include the label's own source {src!r}, "
                f"got {witnesses!r}"
            )

    # dispute exists exactly when the state says the witnesses disagree — an
    # absent dispute on a disputed label loses the only record of WHAT the
    # disagreement was, and a dispute on an agreed label is unreadable.
    dispute = label.get("dispute")
    if state == "disputed" and dispute is None:
        errors.append(f"{path}.dispute is required when state is 'disputed'")
    elif state != "disputed" and dispute is not None:
        errors.append(
            f"{path}.dispute is only allowed when state is 'disputed', got state {state!r}"
        )

    if dispute is not None:
        if not isinstance(dispute, dict):
            errors.append(
                f"{path}.dispute must be an object mapping source -> class_id, "
                f"got {dispute!r}"
            )
            return
        if len(dispute) < 2:
            errors.append(
                f"{path}.dispute must record at least two disagreeing sources, "
                f"got {dispute!r}"
            )
        classes = object_class_ids()
        for src, claimed in dispute.items():
            if src not in LABEL_SOURCES:
                errors.append(
                    f"{path}.dispute key {src!r} must be one of {LABEL_SOURCES}"
                )
            elif witnesses and src not in witnesses:
                errors.append(
                    f"{path}.dispute key {src!r} must also appear in witnesses "
                    f"{witnesses!r}"
                )
            if claimed not in classes:
                errors.append(
                    f"{path}.dispute[{src!r}] must be an id from "
                    f"taxonomies/{OBJECT_CLASS_TAXONOMY}.json, got {claimed!r}"
                )
        if len(set(dispute.values())) < 2:
            errors.append(
                f"{path}.dispute must record differing class_ids, got {dispute!r}"
            )


def validate_scene_graph(graph: object, *, path: str = "scene_graph") -> list[str]:
    """Return a list of errors for one ``scene_graph`` object (empty = valid).

    An empty ``labels`` array is valid — a map with nothing in it yet is a real
    state, distinct from "no scene graph".
    """
    errors: list[str] = []
    if not isinstance(graph, dict):
        errors.append(f"{path} must be a JSON object, got {type(graph).__name__}")
        return errors

    _check_str(graph, "map_id", path, errors)

    revision = graph.get("revision")
    if not _is_int(revision) or revision < 0:
        errors.append(
            f"{path}.revision must be a non-negative int (monotonically increasing "
            f"per map_id), got {revision!r}"
        )

    _check_ns(graph, "updated_at_ns", path, errors)

    labels = graph.get("labels")
    if not isinstance(labels, list):
        errors.append(f"{path}.labels must be an array, got {labels!r}")
        return errors

    seen: dict[str, int] = {}
    for i, label in enumerate(labels):
        _validate_scene_graph_label(label, f"{path}.labels[{i}]", errors)
        if isinstance(label, dict):
            lid = label.get("label_id")
            if isinstance(lid, str) and lid:
                if lid in seen:
                    errors.append(
                        f"{path}.labels[{i}].label_id {lid!r} duplicates "
                        f"labels[{seen[lid]}] — a label_id identifies one object"
                    )
                else:
                    seen[lid] = i
    return errors


# --- colocalization ----------------------------------------------------------


def _validate_colocalization_body(body: dict, path: str, errors: list[str]) -> None:
    _check_str(body, "map_id", path, errors)

    state = body.get("state")
    if state not in COLOCALIZATION_STATES:
        errors.append(
            f"{path}.state must be one of {COLOCALIZATION_STATES}, got {state!r}"
        )

    has_t = "T_map_headset" in body
    if has_t:
        _validate_pose(body["T_map_headset"], f"{path}.T_map_headset", errors)
        _check_ns(body, "computed_at_ns", path, errors)
    if state == "ok" and not has_t:
        errors.append(f"{path}.T_map_headset is required when state is 'ok'")
    if state == "lost" and has_t:
        errors.append(
            f"{path}.T_map_headset must be omitted when state is 'lost' — "
            f"absent means unknown; never publish an identity transform as a stand-in"
        )

    quality = body.get("quality")
    if state == "ok" and quality is None:
        errors.append(f"{path}.quality is required when state is 'ok'")
    if quality is not None:
        if not isinstance(quality, dict):
            errors.append(f"{path}.quality must be an object, got {quality!r}")
        else:
            rmse = quality.get("rmse_m")
            if not _is_finite_number(rmse) or rmse < 0.0:
                errors.append(
                    f"{path}.quality.rmse_m must be a non-negative finite number "
                    f"(metres), got {rmse!r}"
                )
            ratio = quality.get("inlier_ratio")
            if not _is_finite_number(ratio) or ratio < 0.0 or ratio > 1.0:
                errors.append(
                    f"{path}.quality.inlier_ratio must be a number in [0, 1], got {ratio!r}"
                )
            if "match_count" in quality:
                mc = quality["match_count"]
                if not _is_int(mc) or mc < 0:
                    errors.append(
                        f"{path}.quality.match_count must be a non-negative int, got {mc!r}"
                    )

    if "event" in body:
        event = body["event"]
        if event != COLOCALIZATION_STALE_EVENT:
            errors.append(
                f"{path}.event must be {COLOCALIZATION_STALE_EVENT!r} when present, "
                f"got {event!r}"
            )
        elif state == "ok":
            errors.append(
                f"{path}.event {COLOCALIZATION_STALE_EVENT!r} contradicts state 'ok'"
            )

    if "reason" in body:
        _check_str(body, "reason", path, errors)


# --- 8442 messages -----------------------------------------------------------


def validate_ps_message(msg: object, *, path: str = "message") -> list[str]:
    """Return a list of errors for one PS message on the 8442 socket (empty = valid).

    Envelope v1 — ``{type, seq, ts, body}`` — is the C3 header verbatim: these
    messages ride the same socket as teleop, so they carry the same header a
    bridge already demultiplexes on.
    """
    errors: list[str] = []
    if not isinstance(msg, dict):
        errors.append(f"{path} must be a JSON object, got {type(msg).__name__}")
        return errors

    for key in ENVELOPE_KEYS:
        if key not in msg:
            errors.append(f"{path} missing required envelope key: {key}")
    if errors:
        return errors

    mtype = msg["type"]
    if mtype not in PS_MESSAGE_TYPES:
        errors.append(f"{path}.type must be one of {PS_MESSAGE_TYPES}, got {mtype!r}")

    seq = msg["seq"]
    if not _is_int(seq) or seq < 0 or seq > _UINT32_MAX:
        errors.append(f"{path}.seq must be a uint32, got {seq!r}")

    ts = msg["ts"]
    if not _is_int(ts) or ts < 0:
        errors.append(f"{path}.ts must be an int64 Unix nanosecond timestamp, got {ts!r}")

    body = msg["body"]
    if not isinstance(body, dict):
        errors.append(f"{path}.body must be a JSON object, got {body!r}")
        return errors

    if mtype == "semantic_label":
        _check_str(body, "map_id", f"{path}.body", errors)
        labels = body.get("labels")
        if not isinstance(labels, list) or not labels:
            errors.append(
                f"{path}.body.labels must be a non-empty array of ObservationLabel "
                f"(batch, do not burst), got {labels!r}"
            )
        else:
            for i, label in enumerate(labels):
                errors.extend(
                    validate_observation_label(
                        label,
                        path=f"{path}.body.labels[{i}]",
                        allowed_sources=UPLINK_LABEL_SOURCES,
                    )
                )
    elif mtype == "scene_graph":
        errors.extend(validate_scene_graph(body, path=f"{path}.body"))
    elif mtype == "colocalization":
        _validate_colocalization_body(body, f"{path}.body", errors)

    return errors


def validate_ps_stream(messages: list[dict]) -> list[str]:
    """Validate a captured stream of PS messages from **one sender**.

    On top of per-message validity this checks the properties that only exist
    across messages, and that the wire rules actually hinge on:

    - ``seq`` strictly increasing (per type, so a mixed capture still checks),
    - ``ts`` non-decreasing,
    - ``scene_graph.revision`` non-decreasing — the consumer redraws off it,
    - the sustained per-type rate ceiling in :data:`PS_MAX_HZ`. Low frequency is
      the hard requirement of C12: these share the socket with 30 Hz teleop.
    """
    errors: list[str] = []
    last_seq: dict[str, int] = {}
    last_ts: int | None = None
    first_ts: dict[str, int] = {}
    latest_ts: dict[str, int] = {}
    counts: dict[str, int] = {}
    last_revision: int | None = None

    for i, msg in enumerate(messages):
        msg_errors = validate_ps_message(msg, path=f"messages[{i}]")
        errors.extend(msg_errors)
        if msg_errors or not isinstance(msg, dict):
            continue

        mtype, seq, ts = msg["type"], msg["seq"], msg["ts"]

        if mtype in last_seq and seq <= last_seq[mtype]:
            errors.append(
                f"messages[{i}].seq must be strictly increasing per sender "
                f"({last_seq[mtype]} -> {seq})"
            )
        last_seq[mtype] = seq

        if last_ts is not None and ts < last_ts:
            errors.append(f"messages[{i}].ts must be non-decreasing ({last_ts} -> {ts})")
        last_ts = ts

        first_ts.setdefault(mtype, ts)
        latest_ts[mtype] = ts
        counts[mtype] = counts.get(mtype, 0) + 1

        if mtype == "scene_graph":
            revision = msg["body"]["revision"]
            if last_revision is not None and revision < last_revision:
                errors.append(
                    f"messages[{i}].body.revision must be monotonically increasing "
                    f"({last_revision} -> {revision})"
                )
            last_revision = revision

    for mtype, count in counts.items():
        if count < 2:
            continue
        span_ns = latest_ts[mtype] - first_ts[mtype]
        ceiling = PS_MAX_HZ[mtype]
        if span_ns <= 0:
            errors.append(
                f"{count} '{mtype}' messages share one timestamp — exceeds the "
                f"{ceiling} Hz ceiling (batch them into one message)"
            )
            continue
        rate = (count - 1) / (span_ns / 1e9)
        if rate > ceiling:
            errors.append(
                f"'{mtype}' sustained rate {rate:.2f} Hz exceeds the C12 ceiling of "
                f"{ceiling} Hz — must not compete with {TELEOP_FRAME_HZ:.0f} Hz teleop frames"
            )

    return errors
