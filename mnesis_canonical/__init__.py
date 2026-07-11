"""Mnesis Canonical Schema — open standard for embodied spatial-action data.

The reference Python implementation of the Canonical Schema: typed frame,
validation, and JSONL I/O. Apache-2.0. See SPEC.md for the authoritative spec.
"""
from .io import read_jsonl, write_jsonl
from .isaac import (
    from_isaac,
    quat_wxyz_to_xyzw,
    quat_xyzw_to_wxyz,
    to_isaac,
)
from .lerobot import LEROBOT_FEATURES, from_lerobot, to_lerobot
from .manifest import build_manifest, manifest_for_episode, validate_manifest, write_manifest
from .schema import (
    DEVICES,
    MODALITIES,
    REQUIRED_KEYS,
    VECTOR_LENGTHS,
    CanonicalFrame,
)
from .validate import (
    ValidationReport,
    load_json_schema,
    validate_frame,
    validate_frame_jsonschema,
    validate_frames,
)

__version__ = "0.1.0"

__all__ = [
    "CanonicalFrame",
    "REQUIRED_KEYS",
    "VECTOR_LENGTHS",
    "DEVICES",
    "MODALITIES",
    "validate_frame",
    "validate_frames",
    "validate_frame_jsonschema",
    "load_json_schema",
    "ValidationReport",
    "read_jsonl",
    "write_jsonl",
    "to_lerobot",
    "from_lerobot",
    "LEROBOT_FEATURES",
    "build_manifest",
    "manifest_for_episode",
    "validate_manifest",
    "write_manifest",
    "to_isaac",
    "from_isaac",
    "quat_xyzw_to_wxyz",
    "quat_wxyz_to_xyzw",
    "__version__",
]
