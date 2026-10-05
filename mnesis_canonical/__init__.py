"""Mnesis Canonical Schema — open standard for embodied spatial-action data.

The reference Python implementation of the Canonical Schema: typed frame,
validation, and JSONL I/O. Apache-2.0. See SPEC.md for the authoritative spec.
"""

import importlib.metadata as _metadata
from pathlib import Path as _Path

from .embodiment_registry import (
    list_camera_names,
    list_embodiment_ids,
    list_embodiments,
    load_embodiment,
    reference_camera,
)
from .io import read_jsonl, write_jsonl
from .lerobot import LEROBOT_FEATURES, from_lerobot, to_lerobot
from .manifest import (
    CLOCK_SOURCES,
    SIDECAR_KINDS,
    build_manifest,
    clock_errors,
    manifest_for_episode,
    validate_manifest,
    write_manifest,
)
from .recording_manifest import (
    load_recording_manifest,
    load_recording_manifest_schema,
    validate_recording_manifest,
)
from .schema import (
    ANNOTATION_HANDS,
    ANNOTATION_SOURCES,
    ANNOTATION_VISIBILITIES,
    CAMERA_NAME_RE,
    DEFAULT_PROFILE,
    DEVICES,
    EVENT_TYPES,
    EXPERIMENTAL_KEYS,
    FIELD_STATUS,
    GRIPPER_KEYS,
    GRIPPER_MAX,
    GRIPPER_MIN,
    HAND_FRAME_KEY,
    HAND_FRAMES,
    HAND_KEYS,
    HAND_KPTS_KEYS,
    HAND_LAYOUT_KEY,
    HAND_ROT_KEYS,
    HAND_SIDES,
    HAND_SOURCE_KEY,
    IMAGE_KEY_PREFIX,
    MANIPULATION_ACTIONS,
    MODALITIES,
    PROFILES,
    REQUIRED_KEYS,
    ROBOT_V2_VARIABLE_VECTORS,
    VECTOR_LENGTHS,
    VENDOR_EXTENSION_PREFIX,
    CanonicalFrame,
    camera_name,
    get_schema_version,
    image_keys,
    required_keys_for_profile,
)
from .semantic import (
    COLOCALIZATION_MAX_HZ,
    COLOCALIZATION_STALE_EVENT,
    COLOCALIZATION_STATES,
    ENVELOPE_KEYS,
    LABEL_FRAME_IDS,
    LABEL_SOURCES,
    LABEL_STATES,
    OBJECT_CLASS_TAXONOMY,
    PS_MAX_HZ,
    PS_MESSAGE_TYPES,
    SCENE_GRAPH_MAX_HZ,
    SCENE_GRAPH_RATE_HZ,
    SEMANTIC_LABEL_MAX_HZ,
    TELEOP_FRAME_HZ,
    UPLINK_LABEL_SOURCES,
    load_semantic_schema,
    object_class_ids,
    validate_observation_label,
    validate_ps_message,
    validate_ps_message_jsonschema,
    validate_ps_stream,
    validate_scene_graph,
)
from .taxonomy_registry import (
    list_taxonomies,
    list_taxonomy_ids,
    list_term_ids,
    list_terms,
    load_taxonomy,
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

# ── Frozen modules (slim-1, #163) ────────────────────────────────────────────
# The following modules are frozen: ``isaac``, ``migrate``, ``skeleton_registry``,
# ``objects_jsonl`` (C13), ``sdk``, and the ``extensions/`` data directory. They
# are NO LONGER exported from the package top level (neither re-exported here nor
# listed in ``__all__``), but the source files and their tests are kept in place
# and the importable submodules remain available via their full path, e.g.::
#
#     from mnesis_canonical.isaac import to_isaac, from_isaac
#     from mnesis_canonical.migrate import migrate_hand_v0
#     from mnesis_canonical.skeleton_registry import load_skeleton
#     from mnesis_canonical.objects_jsonl import validate_object_record
#     from mnesis_canonical.sdk import DeviceAdapter
#
# ``extensions/`` is a vendor-extension registry data directory (not a Python
# submodule); its ``x-<vendor>.`` convention still lives in ``schema`` via
# ``VENDOR_EXTENSION_PREFIX`` and the JSON Schema patternProperties, which are
# part of the main path and stay exported. Freeze = removed from the public
# top-level API + main docs + CI gate; nothing is deleted (zero-cost rollback).

# ``__version__`` must match the installed dist — the #100 bug was that the
# package reported 0.5.0 while ``pip install`` gave 0.2.0, sending downstream
# debugging the wrong way. The literal below is the authoritative fallback for
# running from a source checkout (not pip-installed); it is kept in sync with
# ``pyproject.toml`` by ``scripts/version_check.py``. When pip-installed the
# value is overridden from the wheel's own metadata so it can never disagree.
__version__ = "0.6.1"
if not (_Path(__file__).resolve().parent.parent / "pyproject.toml").exists():
    try:
        __version__ = _metadata.version("mnesis-canonical")
    except _metadata.PackageNotFoundError:
        pass

__all__ = [
    "CanonicalFrame",
    "DEFAULT_PROFILE",
    "EVENT_TYPES",
    "EXPERIMENTAL_KEYS",
    "FIELD_STATUS",
    "MANIPULATION_ACTIONS",
    "ANNOTATION_HANDS",
    "ANNOTATION_VISIBILITIES",
    "ANNOTATION_SOURCES",
    "PROFILES",
    "IMAGE_KEY_PREFIX",
    "CAMERA_NAME_RE",
    "camera_name",
    "image_keys",
    "REQUIRED_KEYS",
    "ROBOT_V2_VARIABLE_VECTORS",
    "VECTOR_LENGTHS",
    "VENDOR_EXTENSION_PREFIX",
    "GRIPPER_KEYS",
    "GRIPPER_MIN",
    "GRIPPER_MAX",
    "HAND_SIDES",
    "HAND_KEYS",
    "HAND_KPTS_KEYS",
    "HAND_ROT_KEYS",
    "HAND_LAYOUT_KEY",
    "HAND_FRAME_KEY",
    "HAND_SOURCE_KEY",
    "HAND_FRAMES",
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
    "load_recording_manifest",
    "load_recording_manifest_schema",
    "validate_recording_manifest",
    "get_schema_version",
    "to_lerobot",
    "from_lerobot",
    "LEROBOT_FEATURES",
    "build_manifest",
    "manifest_for_episode",
    "validate_manifest",
    "write_manifest",
    "SIDECAR_KINDS",
    "CLOCK_SOURCES",
    "clock_errors",
    "list_embodiments",
    "list_embodiment_ids",
    "load_embodiment",
    "list_camera_names",
    "reference_camera",
    "list_taxonomies",
    "list_taxonomy_ids",
    "list_terms",
    "list_term_ids",
    "load_taxonomy",
    # Dual-endpoint semantic perception (C12)
    "OBJECT_CLASS_TAXONOMY",
    "LABEL_SOURCES",
    "UPLINK_LABEL_SOURCES",
    "LABEL_STATES",
    "LABEL_FRAME_IDS",
    "COLOCALIZATION_STATES",
    "COLOCALIZATION_STALE_EVENT",
    "PS_MESSAGE_TYPES",
    "ENVELOPE_KEYS",
    "PS_MAX_HZ",
    "SCENE_GRAPH_RATE_HZ",
    "SCENE_GRAPH_MAX_HZ",
    "SEMANTIC_LABEL_MAX_HZ",
    "COLOCALIZATION_MAX_HZ",
    "TELEOP_FRAME_HZ",
    "object_class_ids",
    "validate_observation_label",
    "validate_scene_graph",
    "validate_ps_message",
    "validate_ps_message_jsonschema",
    "validate_ps_stream",
    "load_semantic_schema",
    "__version__",
]
