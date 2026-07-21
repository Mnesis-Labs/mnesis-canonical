"""Mnesis Canonical Schema — open standard for embodied spatial-action data.

The reference Python implementation of the Canonical Schema: typed frame,
validation, and JSONL I/O. Apache-2.0. See SPEC.md for the authoritative spec.
"""
from .embodiment_registry import list_embodiment_ids, list_embodiments, load_embodiment
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
    ANNOTATION_HANDS,
    ANNOTATION_SOURCES,
    ANNOTATION_VISIBILITIES,
    DEFAULT_PROFILE,
    DEVICES,
    EVENT_TYPES,
    GRIPPER_KEYS,
    GRIPPER_MAX,
    GRIPPER_MIN,
    MANIPULATION_ACTIONS,
    MODALITIES,
    PROFILES,
    REQUIRED_KEYS,
    ROBOT_V2_VARIABLE_VECTORS,
    VECTOR_LENGTHS,
    CanonicalFrame,
    get_schema_version,
    required_keys_for_profile,
)
from .validate import (
    ValidationReport,
    load_json_schema,
    validate_annotations,
    validate_events,
    validate_frame,
    validate_frame_jsonschema,
    validate_frames,
)

__version__ = "0.3.0"

__all__ = [
    "CanonicalFrame",
    "DEFAULT_PROFILE",
    "EVENT_TYPES",
    "MANIPULATION_ACTIONS",
    "ANNOTATION_HANDS",
    "ANNOTATION_VISIBILITIES",
    "ANNOTATION_SOURCES",
    "PROFILES",
    "REQUIRED_KEYS",
    "ROBOT_V2_VARIABLE_VECTORS",
    "VECTOR_LENGTHS",
    "GRIPPER_KEYS",
    "GRIPPER_MIN",
    "GRIPPER_MAX",
    "DEVICES",
    "MODALITIES",
    "required_keys_for_profile",
    "validate_frame",
    "validate_frames",
    "validate_frame_jsonschema",
    "validate_events",
    "validate_annotations",
    "load_json_schema",
    "ValidationReport",
    "read_jsonl",
    "write_jsonl",
    "get_schema_version",
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
    "list_embodiments",
    "list_embodiment_ids",
    "load_embodiment",
    "__version__",
]
