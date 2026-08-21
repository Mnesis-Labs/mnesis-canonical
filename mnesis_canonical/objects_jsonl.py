"""objects.jsonl — object-track side channel (C13).

A capture pipeline that also runs 2-D object detection over its frames (the
Video2Robo trajectory work, Mnesis-Daedalus ``scene/object_track.py``) can emit
an ``objects.jsonl`` file **alongside** the frame-level JSONL: one header line
describing the file, then one line per per-frame per-object observation. This
module defines and validates that side channel. It is additive-only — a
consumer that has never heard of ``objects.jsonl`` reads the frame-level JSONL
exactly as before, and nothing here ever touches a frame-level field.

The single rule this module exists to enforce, not merely document:

``pose_dof``
    A single camera view's 2-D box + depth back-projection structurally
    observes **position only** — three degrees of freedom. It cannot observe
    orientation. So every record says so: ``pose_dof: 3`` with
    ``quat_wxyz: null``. A record from a real orientation estimator instead
    says ``pose_dof: 6`` with a populated unit quaternion. What is never
    allowed is publishing a placeholder quaternion (identity, zeros) under
    ``pose_dof: 3`` to make a position-only observation look like a full pose —
    the schema and this module both make that combination invalid rather than
    merely discouraged (same discipline as C12's ``ObservationLabel`` refusing
    a non-``map`` ``frame_id``, or a colocalization record with ``state:"lost"``
    still carrying a transform).

``quat_wxyz`` is ``[w, x, y, z]`` — **scalar first**, matching
Mnesis-Daedalus's own ``scene/types.py`` (MuJoCo convention). This is a
deliberate departure from C12's ``pose.q``, which is scalar-**last**
``[x, y, z, w]``. Two different producers picked two different, both
internally-consistent conventions before this side channel was registered;
recording the divergence here is more honest than quietly picking a winner and
asking Daedalus to re-emit history.

``class_id`` here is whatever the 2-D detector backend calls it
(``lerobot.perception.detector.Detector`` is backend-swappable and
open-vocabulary) — it is **not** drawn from ``taxonomies/object_class_v1.json``
(C12). Harmonising the two vocabularies is a natural follow-up, not a v1
requirement; do not assume they already agree.

See SPEC.md §objects.jsonl side channel / CONTRACTS.md C13. Keep in lock-step
with ``objects_jsonl.schema.json``.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import TypeGuard

_SCHEMA_PATH = Path(__file__).resolve().parent / "objects_jsonl.schema.json"

SCHEMA_VERSION = 1

#: frames_dir layouts the extractor recognises (Mnesis-Daedalus scene/capture.py
#: vs. scene/iris_bridge.py). Informational on the header — does not change how
#: this file itself is read.
FRAME_DIALECTS = ("mono", "iris")

#: The only pose frame defined so far. A record in any other frame is not
#: fusable and must be transformed before publishing — same rule as C12's
#: ``LABEL_FRAME_IDS``.
POSE_FRAME = "map"

#: The only two honest values. See the module docstring — this is the field the
#: whole contract exists to police.
POSE_DOFS = (3, 6)

#: Tolerance on ``|q| == 1`` for a 6-DoF record's orientation, mirroring C12's
#: ``QUAT_NORM_TOLERANCE``.
QUAT_NORM_TOLERANCE = 1e-3


def load_objects_jsonl_schema() -> dict:
    """Load the bundled objects.jsonl JSON Schema (Draft 2020-12) as a dict."""
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def validate_line_jsonschema(line: dict) -> list[str]:
    """Validate one objects.jsonl line (header or object record) against the
    bundled JSON Schema.

    Requires the optional ``jsonschema`` dependency (``pip install
    mnesis-canonical[jsonschema]``). Structure/types/the pose_dof<->quat_wxyz
    coupling only — the cross-line rules (header.pose_dof matching every
    record, frame monotonicity, track-count bookkeeping) live in
    :func:`validate_objects_jsonl_stream`.
    """
    try:
        import jsonschema
    except ImportError as e:  # pragma: no cover - exercised only without extra
        raise RuntimeError(
            "validate_line_jsonschema requires the optional 'jsonschema' "
            "dependency; install with: pip install mnesis-canonical[jsonschema]"
        ) from e
    validator = jsonschema.Draft202012Validator(load_objects_jsonl_schema())
    return [err.message for err in sorted(validator.iter_errors(line), key=str)]


# --- helpers -----------------------------------------------------------------


def _is_number(v: object) -> TypeGuard[int | float]:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_finite_number(v: object) -> TypeGuard[int | float]:
    return _is_number(v) and math.isfinite(float(v))


def _is_int(v: object) -> TypeGuard[int]:
    return isinstance(v, int) and not isinstance(v, bool)


def _check_str(obj: dict, key: str, path: str, errors: list[str]) -> None:
    val = obj.get(key)
    if not isinstance(val, str) or not val:
        errors.append(f"{path}.{key} must be a non-empty string, got {val!r}")


def _check_vector(
    obj: dict,
    key: str,
    length: int,
    path: str,
    errors: list[str],
) -> list[float] | None:
    val = obj.get(key)
    if not isinstance(val, list) or len(val) != length:
        errors.append(f"{path}.{key} must be a list of {length} numbers, got {val!r}")
        return None
    if not all(_is_finite_number(x) for x in val):
        errors.append(f"{path}.{key} must contain only finite numbers, got {val!r}")
        return None
    return [float(x) for x in val]


# --- header --------------------------------------------------------------


def validate_header(header: object, *, path: str = "header") -> list[str]:
    """Return a list of errors for the objects.jsonl header line (empty = valid)."""
    errors: list[str] = []
    if not isinstance(header, dict):
        errors.append(f"{path} must be a JSON object, got {type(header).__name__}")
        return errors

    if header.get("type") != "header":
        errors.append(f"{path}.type must be 'header', got {header.get('type')!r}")

    version = header.get("version")
    if version != SCHEMA_VERSION:
        errors.append(
            f"{path}.version must be {SCHEMA_VERSION} (only version currently "
            f"defined), got {version!r}"
        )

    _check_str(header, "source", path, errors)

    dialect = header.get("frame_dialect")
    if dialect not in FRAME_DIALECTS:
        errors.append(f"{path}.frame_dialect must be one of {FRAME_DIALECTS}, got {dialect!r}")

    if "detector_backend" in header:
        _check_str(header, "detector_backend", path, errors)

    pose_frame = header.get("pose_frame")
    if pose_frame != POSE_FRAME:
        errors.append(f"{path}.pose_frame must be {POSE_FRAME!r}, got {pose_frame!r}")

    pose_dof = header.get("pose_dof")
    if pose_dof not in POSE_DOFS:
        errors.append(f"{path}.pose_dof must be one of {POSE_DOFS}, got {pose_dof!r}")

    for key in ("num_frames", "num_tracks"):
        val = header.get(key)
        if not _is_int(val) or val < 0:
            errors.append(f"{path}.{key} must be a non-negative int, got {val!r}")

    return errors


# --- object record -------------------------------------------------------


def validate_object_record(record: object, *, path: str = "object") -> list[str]:
    """Return a list of errors for one object-observation line (empty = valid)."""
    errors: list[str] = []
    if not isinstance(record, dict):
        errors.append(f"{path} must be a JSON object, got {type(record).__name__}")
        return errors

    if record.get("type") != "object":
        errors.append(f"{path}.type must be 'object', got {record.get('type')!r}")

    frame = record.get("frame")
    if not _is_int(frame) or frame < 0:
        errors.append(f"{path}.frame must be a non-negative int, got {frame!r}")

    _check_str(record, "track_id", path, errors)
    _check_str(record, "class_id", path, errors)

    confidence = record.get("confidence")
    if not _is_finite_number(confidence) or not 0.0 <= confidence <= 1.0:
        errors.append(f"{path}.confidence must be a finite number in [0, 1], got {confidence!r}")

    pose_dof = record.get("pose_dof")
    if pose_dof not in POSE_DOFS:
        errors.append(f"{path}.pose_dof must be one of {POSE_DOFS}, got {pose_dof!r}")

    _check_vector(record, "position_m", 3, path, errors)

    # The rule the whole contract exists to enforce — see module docstring.
    quat = record.get("quat_wxyz")
    if pose_dof == 3:
        if quat is not None:
            errors.append(
                f"{path}.quat_wxyz must be null when pose_dof is 3 — a single-view "
                f"2-D box + depth observation cannot observe orientation; got {quat!r} "
                f"(never publish a placeholder quaternion to make a 3-DoF observation "
                f"look like 6-DoF)"
            )
    elif pose_dof == 6:
        q = _check_vector(record, "quat_wxyz", 4, path, errors)
        if q is not None:
            norm = math.sqrt(sum(x * x for x in q))
            if abs(norm - 1.0) > QUAT_NORM_TOLERANCE:
                errors.append(
                    f"{path}.quat_wxyz must be a unit quaternion [w,x,y,z] "
                    f"(|q| = 1 ± {QUAT_NORM_TOLERANCE}), got |q| = {norm:.6f}"
                )

    depth = record.get("depth_m")
    if not _is_finite_number(depth) or depth <= 0.0:
        errors.append(f"{path}.depth_m must be a positive finite number, got {depth!r}")

    box = record.get("box_xyxy")
    if not isinstance(box, list) or len(box) != 4 or not all(_is_finite_number(x) for x in box):
        errors.append(f"{path}.box_xyxy must be a list of 4 finite numbers, got {box!r}")
    else:
        x1, y1, x2, y2 = (float(x) for x in box)
        if not (x1 < x2 and y1 < y2):
            errors.append(f"{path}.box_xyxy must satisfy x1 < x2 and y1 < y2, got {box!r}")

    for key in ("width_m", "height_m"):
        val = record.get(key)
        if not _is_finite_number(val) or val <= 0.0:
            errors.append(f"{path}.{key} must be a positive finite number, got {val!r}")

    return errors


# --- stream ---------------------------------------------------------------


def validate_objects_jsonl_stream(lines: list[dict]) -> list[str]:
    """Validate a full objects.jsonl file (already parsed to a list of dicts).

    On top of per-line validity this checks the invariants that only exist
    across lines:

    - the first line is the header, and there is exactly one,
    - every object record's ``pose_dof`` equals the header's — a per-record
      override is a producer bug, not a per-object feature,
    - ``frame`` is non-decreasing across the file (capture order),
    - the number of distinct ``track_id`` values equals ``header.num_tracks``.
    """
    errors: list[str] = []
    if not lines:
        errors.append("objects.jsonl must contain at least a header line, got an empty file")
        return errors

    header = lines[0]
    errors.extend(validate_header(header, path="lines[0]"))
    header_pose_dof = header.get("pose_dof") if isinstance(header, dict) else None
    header_num_tracks = header.get("num_tracks") if isinstance(header, dict) else None

    extra_headers = [
        i
        for i, ln in enumerate(lines[1:], start=1)
        if isinstance(ln, dict) and ln.get("type") == "header"
    ]
    if extra_headers:
        errors.append(
            f"lines{extra_headers} are additional 'header' lines — exactly one "
            f"header is allowed, at lines[0]"
        )

    last_frame: int | None = None
    track_ids: set[str] = set()
    for i, record in enumerate(lines[1:], start=1):
        if isinstance(record, dict) and record.get("type") == "header":
            continue  # already reported above
        errors.extend(validate_object_record(record, path=f"lines[{i}]"))
        if not isinstance(record, dict):
            continue

        pose_dof = record.get("pose_dof")
        if header_pose_dof in (3, 6) and pose_dof in (3, 6) and pose_dof != header_pose_dof:
            errors.append(
                f"lines[{i}].pose_dof ({pose_dof}) does not match "
                f"header.pose_dof ({header_pose_dof}) — one file, one dof"
            )

        frame = record.get("frame")
        if _is_int(frame):
            if last_frame is not None and frame < last_frame:
                errors.append(
                    f"lines[{i}].frame must be non-decreasing across the file "
                    f"({last_frame} -> {frame})"
                )
            last_frame = frame

        track_id = record.get("track_id")
        if isinstance(track_id, str) and track_id:
            track_ids.add(track_id)

    if _is_int(header_num_tracks) and len(track_ids) != header_num_tracks:
        errors.append(
            f"header.num_tracks ({header_num_tracks}) does not match the "
            f"{len(track_ids)} distinct track_id value(s) actually observed"
        )

    return errors
