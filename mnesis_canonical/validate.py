"""Validation for the Mnesis Canonical Schema.

`validate_frame(dict) -> list[str]` returns a list of human-readable errors
(empty = valid). `validate_jsonl(path) -> ValidationReport` validates a whole
episode sidecar. Used by Mnesis Ambrosia's ingest gate and by capture-surface CI.

Profile-aware validation (v0.2+):
  - ``ego_v1`` (default when absent): fixed-length vectors, ``observation.images.ego`` required.
  - ``robot_v2``: variable-length ``observation.state`` and ``action``, open camera-key set,
    optional ``observation.eef_pose.{left,right}``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .schema import (
    ANNOTATION_HANDS,
    ANNOTATION_SOURCES,
    ANNOTATION_VISIBILITIES,
    DEFAULT_PROFILE,
    DEVICES,
    EVENT_TYPES,
    INT_KEYS,
    MANIPULATION_ACTIONS,
    MODALITIES,
    PROFILES,
    ROBOT_V2_VARIABLE_VECTORS,
    VECTOR_LENGTHS,
    required_keys_for_profile,
)

_SCHEMA_PATH = Path(__file__).resolve().parent / "canonical_frame.schema.json"


def load_json_schema() -> dict:
    """Load the bundled JSON Schema (Draft 2020-12) as a dict.

    This is the same contract as the pure-Python validator below; it exists so
    that other languages / tools (e.g. Mnesis Ambrosia ingest) can validate
    against the standard without a Python dependency.
    """
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def validate_frame_jsonschema(frame: dict) -> list[str]:
    """Validate one frame against the bundled JSON Schema via the optional
    ``jsonschema`` backend (install with ``pip install mnesis-canonical[jsonschema]``).

    Returns a list of human-readable errors (empty = valid). Raises RuntimeError
    if ``jsonschema`` is not installed. Note: this enforces structure/types only;
    cross-frame rules (frame_index monotonicity) and strict vocab live in the
    pure-Python :func:`validate_frame` / :func:`validate_frames`.
    """
    try:
        import jsonschema
    except ImportError as e:  # pragma: no cover - exercised only without extra
        raise RuntimeError(
            "validate_frame_jsonschema requires the optional 'jsonschema' "
            "dependency; install with: pip install mnesis-canonical[jsonschema]"
        ) from e
    validator = jsonschema.Draft202012Validator(load_json_schema())
    return [err.message for err in sorted(validator.iter_errors(frame), key=str)]


def _get_profile(frame: dict) -> str:
    """Return the profile name for a frame, defaulting to ``DEFAULT_PROFILE``."""
    p = frame.get("profile")
    if p is None:
        return DEFAULT_PROFILE
    return p


def _validate_vector_field(
    frame: dict, key: str, expected_len: int, errors: list[str],
) -> None:
    """Validate a fixed-length vector field (used for ego_v1 profile)."""
    val = frame.get(key)
    if val is None:
        return  # missing-key error handled elsewhere
    if not isinstance(val, list):
        errors.append(f"{key} must be a list")
        return
    if len(val) != expected_len:
        errors.append(f"{key} must have length {expected_len}, got {len(val)}")
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in val):
        errors.append(f"{key} must contain only numbers")
        return
    # Reject NaN / Inf in vector fields
    import math
    for i, x in enumerate(val):
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            errors.append(f"{key}[{i}] must be a finite number, got {x!r}")
            break  # one error per vector is enough


def validate_frame(frame: dict, *, strict_vocab: bool = False) -> list[str]:
    """Return a list of errors for one frame dict (empty list = valid).

    strict_vocab=True rejects unknown source.device / source.modality values
    (default lenient: unknown vocab is a soft pass so new capture surfaces work).
    """
    errors: list[str] = []
    profile = _get_profile(frame)

    # Validate profile value if present
    if "profile" in frame and frame["profile"] not in PROFILES:
        errors.append(
            f"profile must be one of {PROFILES}, got {frame['profile']!r}"
        )
        # If profile is invalid, fall back to ego_v1 for remaining checks
        profile = DEFAULT_PROFILE

    # Use profile-specific required keys
    required = required_keys_for_profile(profile)
    for key in required:
        if key not in frame:
            errors.append(f"missing required key: {key}")
    if errors:
        return errors  # don't cascade if keys are missing

    for key in INT_KEYS:
        if not isinstance(frame[key], int) or isinstance(frame[key], bool):
            errors.append(f"{key} must be int, got {type(frame[key]).__name__}")

    if not isinstance(frame["timestamp"], str) or not frame["timestamp"]:
        errors.append("timestamp must be a non-empty string")

    # --- Vector field validation (profile-aware) ---
    for key, expected_len in VECTOR_LENGTHS.items():
        if key in ROBOT_V2_VARIABLE_VECTORS and profile == "robot_v2":
            # Variable-length: check type only, no fixed-size constraint
            val = frame.get(key)
            if val is not None:
                if not isinstance(val, list):
                    errors.append(f"{key} must be a list")
                elif not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in val):
                    errors.append(f"{key} must contain only numbers")
                else:
                    import math
                    for i, x in enumerate(val):
                        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
                            errors.append(f"{key}[{i}] must be a finite number, got {x!r}")
                            break
        else:
            _validate_vector_field(frame, key, expected_len, errors)

    # --- observation.images validation (profile-aware) ---
    if profile == "robot_v2":
        # robot_v2: at least one observation.images.<cam> must exist
        img_keys = [k for k in frame if k.startswith("observation.images.")]
        if not img_keys:
            errors.append(
                "robot_v2 profile requires at least one observation.images.<cam> key"
            )
        for k in img_keys:
            if not isinstance(frame[k], str):
                errors.append(f"{k} must be a string (file reference, '' allowed)")
    else:
        # ego_v1: observation.images.ego is required (already checked above)
        if not isinstance(frame["observation.images.ego"], str):
            errors.append("observation.images.ego must be a string (file reference, '' allowed)")

    if not isinstance(frame["tracking_state"], str):
        errors.append("tracking_state must be a string")

    if "spatial_anchor_id" in frame and frame["spatial_anchor_id"] is not None:
        if not isinstance(frame["spatial_anchor_id"], str):
            errors.append("spatial_anchor_id must be a string or null")
        elif frame["spatial_anchor_id"] == "":
            errors.append("spatial_anchor_id must be a non-empty string or null")

    # --- embodiment_id validation ---
    if "embodiment_id" in frame and frame["embodiment_id"] is not None:
        if not isinstance(frame["embodiment_id"], str):
            errors.append("embodiment_id must be a string or null")
        elif not frame["embodiment_id"]:
            errors.append("embodiment_id must be a non-empty string or null")

    # --- robot_v2 optional eef_pose validation ---
    if "observation.eef_pose.left" in frame:
        val = frame["observation.eef_pose.left"]
        if not isinstance(val, list) or len(val) != 7:
            errors.append("observation.eef_pose.left must be a list of length 7")
        elif not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in val):
            errors.append("observation.eef_pose.left must contain only numbers")
    if "observation.eef_pose.right" in frame:
        val = frame["observation.eef_pose.right"]
        if not isinstance(val, list) or len(val) != 7:
            errors.append("observation.eef_pose.right must be a list of length 7")
        elif not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in val):
            errors.append("observation.eef_pose.right must contain only numbers")

    # --- optional gripper channel validation (v0.4+, all profiles) ---
    # Additive: absence = source provides no gripper info (NOT 0.0). When present,
    # must be a finite number normalized to the closed interval [0.0, 1.0]
    # (0.0 = fully open, 1.0 = fully closed).
    if "action.gripper" in frame:
        g = frame["action.gripper"]
        if not isinstance(g, (int, float)) or isinstance(g, bool):
            errors.append(
                f"action.gripper must be a number in [0.0, 1.0], "
                f"got {type(g).__name__}"
            )
        else:
            import math
            if isinstance(g, float) and (math.isnan(g) or math.isinf(g)):
                errors.append(
                    f"action.gripper must be a finite number in [0.0, 1.0], got {g!r}"
                )
            elif g < 0.0 or g > 1.0:
                errors.append(
                    f"action.gripper must be in [0.0, 1.0], got {g}"
                )

    dev, mod = frame["source.device"], frame["source.modality"]
    if not isinstance(dev, str) or not isinstance(mod, str):
        errors.append("source.device / source.modality must be strings")
    elif strict_vocab:
        if dev not in DEVICES:
            errors.append(f"source.device '{dev}' not in {DEVICES}")
        if mod not in MODALITIES:
            errors.append(f"source.modality '{mod}' not in {MODALITIES}")

    return errors


@dataclass
class ValidationReport:
    total: int = 0
    valid: int = 0
    errors: list[tuple[int, str]] = field(default_factory=list)  # (line_no, message)

    @property
    def ok(self) -> bool:
        return self.total > 0 and not self.errors


def validate_frames(frames: list[dict], *, strict_vocab: bool = False) -> ValidationReport:
    report = ValidationReport()
    prev_frame_index: int | None = None

    # --- Episode-level: spatial_anchor_id validation ---
    # Track anchor_ids that have been defined (non-None, non-empty, first occurrence).
    defined_anchors: dict[str, int] = {}  # anchor_id -> first-definition line index

    for i, frame in enumerate(frames):
        report.total += 1
        errs = validate_frame(frame, strict_vocab=strict_vocab)

        # Check for negative frame_index
        if not errs and "frame_index" in frame:
            fi = frame["frame_index"]
            if isinstance(fi, int) and fi < 0:
                errs.append(f"frame_index must be non-negative, got {fi}")
        # Check for duplicate frame_index
        if not errs and prev_frame_index is not None and "frame_index" in frame:
            if frame["frame_index"] == prev_frame_index:
                errs.append(
                    f"duplicate frame_index ({frame['frame_index']}) at line {i}"
                )
            elif frame["frame_index"] < prev_frame_index:
                errs.append(
                    f"frame_index not increasing ({prev_frame_index} -> {frame['frame_index']})"
                )

        # --- spatial_anchor_id validation ---
        aid = frame.get("spatial_anchor_id")
        if aid is not None and isinstance(aid, str) and aid:
            if aid in defined_anchors:
                first_line = defined_anchors[aid]
                errs.append(
                    f"duplicate spatial_anchor_id '{aid}' at line {i} "
                    f"(first defined at line {first_line})"
                )
            else:
                defined_anchors[aid] = i

        if not errs:
            report.valid += 1
            prev_frame_index = frame["frame_index"]
        else:
            for e in errs:
                report.errors.append((i, e))
    return report


def validate_events(episode_dir: str | Path) -> list[str]:
    """Validate the optional ``events.jsonl`` sidecar in an episode directory.

    Returns a list of error messages (empty = valid).  If the file does not exist
    the check passes silently (additive-only — existing episodes without events
    are unaffected).

    Each event line must be a JSON object with:
      - ``t_ns``: int
      - ``type``: one of ``EVENT_TYPES``
      - ``payload``: any JSON value (required, may be null)
    """
    events_path = Path(episode_dir) / "events.jsonl"
    if not events_path.exists():
        return []

    errors: list[str] = []
    with open(events_path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                errors.append(f"events.jsonl line {line_no}: blank line (expected JSON object)")
                continue

            try:
                event = json.loads(line)
            except ValueError as e:
                errors.append(f"events.jsonl line {line_no}: invalid JSON: {e}")
                continue

            if not isinstance(event, dict):
                errors.append(
                    f"events.jsonl line {line_no}: expected JSON object, got {type(event).__name__}"
                )
                continue

            # t_ns must be an int
            t_ns = event.get("t_ns")
            if not isinstance(t_ns, int) or isinstance(t_ns, bool):
                errors.append(
                    f"events.jsonl line {line_no}: t_ns must be an int, "
                    f"got {type(t_ns).__name__ if t_ns is not None else 'null'}"
                )

            # type must be a known event type
            ev_type = event.get("type")
            if not isinstance(ev_type, str):
                errors.append(
                    f"events.jsonl line {line_no}: type must be a string, "
                    f"got {type(ev_type).__name__ if ev_type is not None else 'null'}"
                )
            elif ev_type not in EVENT_TYPES:
                errors.append(
                    f"events.jsonl line {line_no}: unknown event type {ev_type!r}, "
                    f"must be one of {EVENT_TYPES}"
                )

            # payload must be present (may be null)
            if "payload" not in event:
                errors.append(f"events.jsonl line {line_no}: missing required key 'payload'")

    return errors


def validate_annotations(episode_dir: str | Path) -> list[str]:
    """Validate the optional ``annotations/spans.jsonl`` sidecar in an episode dir.

    Returns a list of error messages (empty = valid).  If the file does not exist
    the check passes silently (additive-only — existing episodes without annotations
    are unaffected).

    Each span line must be a JSON object with:
      - ``span_id``: str (required)
      - ``t_start_ns``: int (required, must be < t_end_ns)
      - ``t_end_ns``: int (required, must be > t_start_ns)
      - ``hand``: one of ANNOTATION_HANDS (required)
      - ``action``: one of MANIPULATION_ACTIONS (required)
      - ``action_text``: str (optional, free-text description)
      - ``object``: str (optional, target object label)
      - ``visibility``: one of ANNOTATION_VISIBILITIES (optional)
      - ``confidence``: float 0-1 (optional)
      - ``source``: one of ANNOTATION_SOURCES (optional)
      - ``verified``: bool (optional)
    """
    spans_path = Path(episode_dir) / "annotations" / "spans.jsonl"
    if not spans_path.exists():
        return []

    errors: list[str] = []
    with open(spans_path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                errors.append(
                    f"annotations/spans.jsonl line {line_no}: blank line "
                    f"(expected JSON object)"
                )
                continue

            try:
                span = json.loads(line)
            except ValueError as e:
                errors.append(
                    f"annotations/spans.jsonl line {line_no}: invalid JSON: {e}"
                )
                continue

            if not isinstance(span, dict):
                errors.append(
                    f"annotations/spans.jsonl line {line_no}: expected JSON object, "
                    f"got {type(span).__name__}"
                )
                continue

            # --- Required fields ---

            # span_id
            span_id = span.get("span_id")
            if not isinstance(span_id, str) or not span_id:
                errors.append(
                    f"annotations/spans.jsonl line {line_no}: span_id must be a "
                    f"non-empty string"
                )

            # t_start_ns / t_end_ns
            t_start = span.get("t_start_ns")
            t_end = span.get("t_end_ns")
            if not isinstance(t_start, int) or isinstance(t_start, bool):
                errors.append(
                    f"annotations/spans.jsonl line {line_no}: t_start_ns must be an "
                    f"int, got {type(t_start).__name__ if t_start is not None else 'null'}"
                )
            if not isinstance(t_end, int) or isinstance(t_end, bool):
                errors.append(
                    f"annotations/spans.jsonl line {line_no}: t_end_ns must be an "
                    f"int, got {type(t_end).__name__ if t_end is not None else 'null'}"
                )
            if (
                isinstance(t_start, int)
                and isinstance(t_end, int)
                and not isinstance(t_start, bool)
                and not isinstance(t_end, bool)
            ):
                if t_start >= t_end:
                    errors.append(
                        f"annotations/spans.jsonl line {line_no}: t_start_ns ({t_start}) "
                        f"must be less than t_end_ns ({t_end})"
                    )

            # hand
            hand = span.get("hand")
            if hand not in ANNOTATION_HANDS:
                errors.append(
                    f"annotations/spans.jsonl line {line_no}: hand must be one of "
                    f"{ANNOTATION_HANDS}, got {hand!r}"
                )

            # action
            action = span.get("action")
            if action not in MANIPULATION_ACTIONS:
                errors.append(
                    f"annotations/spans.jsonl line {line_no}: action must be one of "
                    f"{MANIPULATION_ACTIONS}, got {action!r}"
                )

            # --- Optional fields ---

            # confidence (0-1)
            confidence = span.get("confidence")
            if confidence is not None:
                if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
                    errors.append(
                        f"annotations/spans.jsonl line {line_no}: confidence must be "
                        f"a number, got {type(confidence).__name__}"
                    )
                elif confidence < 0.0 or confidence > 1.0:
                    errors.append(
                        f"annotations/spans.jsonl line {line_no}: confidence must be "
                        f"in [0, 1], got {confidence}"
                    )

            # visibility
            visibility = span.get("visibility")
            if visibility is not None and visibility not in ANNOTATION_VISIBILITIES:
                errors.append(
                    f"annotations/spans.jsonl line {line_no}: visibility must be one of "
                    f"{ANNOTATION_VISIBILITIES}, got {visibility!r}"
                )

            # source
            source = span.get("source")
            if source is not None and source not in ANNOTATION_SOURCES:
                errors.append(
                    f"annotations/spans.jsonl line {line_no}: source must be one of "
                    f"{ANNOTATION_SOURCES}, got {source!r}"
                )

            # verified
            verified = span.get("verified")
            if verified is not None and not isinstance(verified, bool):
                errors.append(
                    f"annotations/spans.jsonl line {line_no}: verified must be a bool, "
                    f"got {type(verified).__name__}"
                )

            # action_text (optional, free-text string if present)
            action_text = span.get("action_text")
            if action_text is not None and not isinstance(action_text, str):
                errors.append(
                    f"annotations/spans.jsonl line {line_no}: action_text must be a string"
                )

            # object (optional, free-text string if present)
            obj = span.get("object")
            if obj is not None and not isinstance(obj, str):
                errors.append(
                    f"annotations/spans.jsonl line {line_no}: object must be a string"
                )

    return errors