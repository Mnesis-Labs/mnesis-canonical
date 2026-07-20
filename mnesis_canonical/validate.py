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
    DEFAULT_PROFILE,
    DEVICES,
    INT_KEYS,
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