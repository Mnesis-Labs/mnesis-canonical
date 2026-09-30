"""Public-API slim gate (#163, sprint slim-1).

Locks the freeze contract for the slim-1 cut of the public API:

* **main path** — names that MUST stay exported from the package top level
  (``schema`` / ``validate`` / ``io`` / ``lerobot`` / ``manifest`` /
  ``embodiment_registry`` / ``importers``). Removing any of these is a break.
* **frozen** — names that MUST NOT leak at the package top level
  (``isaac`` / ``migrate`` / ``skeleton_registry`` / ``objects_jsonl`` (C13) /
  ``sdk``). They are still importable via their submodule path (third test).
* ``extensions/`` is a repo-root data directory (registry.json + schema), not a
  Python submodule, and has no top-level exports to assert against; its
  ``x-<vendor>.`` convention still lives in ``schema`` via
  ``VENDOR_EXTENSION_PREFIX`` (a main-path name, asserted to stay exported).

Freeze = removed from top-level exports + main docs + CI gate; nothing is
deleted (zero-cost rollback). See ``mnesis_canonical/__init__.py`` §Frozen.
"""
from __future__ import annotations

import importlib

import mnesis_canonical as mc

# ── Main path: these names MUST stay at the package top level ─────────────────
# Covers the card's minimum (validate_frames, to_lerobot, from_lerobot,
# read_jsonl, write_jsonl, build_manifest, validate_manifest, load_embodiment,
# list_embodiment_ids) plus the rest of the main-path surface.
MAIN_PATH_NAMES = [
    # validate / schema
    "validate_frame",
    "validate_frames",
    "validate_frame_jsonschema",
    "validate_events",
    "validate_annotations",
    "load_json_schema",
    "ValidationReport",
    "CanonicalFrame",
    "get_schema_version",
    "required_keys_for_profile",
    "camera_name",
    "image_keys",
    # io
    "read_jsonl",
    "write_jsonl",
    # lerobot
    "to_lerobot",
    "from_lerobot",
    "LEROBOT_FEATURES",
    # manifest
    "build_manifest",
    "manifest_for_episode",
    "validate_manifest",
    "write_manifest",
    "SIDECAR_KINDS",
    "CLOCK_SOURCES",
    "clock_errors",
    # embodiment registry
    "load_embodiment",
    "list_embodiment_ids",
    "list_embodiments",
    "list_camera_names",
    "reference_camera",
]


def test_main_path_names_still_exported():
    """Every main-path name is still exported at the package top level."""
    missing = [name for name in MAIN_PATH_NAMES if not hasattr(mc, name)]
    assert missing == [], f"main-path names missing from top level: {missing}"

    # importers public entry points (names per source: importers/__init__.py).
    # ``importers`` is accessed via its submodule — it was never re-exported at
    # the package top level — so the entry points themselves are checked there.
    importers = importlib.import_module("mnesis_canonical.importers")
    for entry in ("import_pickle", "import_mcap"):
        assert hasattr(importers, entry), f"mnesis_canonical.importers.{entry} missing"


# ── Frozen: these names MUST NOT be at the package top level ──────────────────
# isaac / migrate / skeleton_registry / objects_jsonl were exported at the top
# level before #163; ``sdk`` was not (its classes live under mnesis_canonical.sdk)
# but is frozen too per the #163 card + slim-1 plan, so the sdk classes are
# asserted to stay out of the top level as well.
FROZEN_NAMES = [
    # isaac
    "from_isaac",
    "to_isaac",
    "quat_wxyz_to_xyzw",
    "quat_wxyz_to_wxyz",
    # migrate
    "migrate_hand_v0",
    "migrate_hand_v0_frames",
    # skeleton_registry
    "joint_count",
    "list_skeleton_ids",
    "list_skeletons",
    "load_skeleton",
    # objects_jsonl (C13)
    "FRAME_DIALECTS",
    "POSE_DOFS",
    "POSE_FRAME",
    "load_objects_jsonl_schema",
    "validate_object_record",
    "validate_objects_jsonl_stream",
    "validate_objects_jsonl_header",
    "validate_objects_jsonl_line_jsonschema",
    # sdk (frozen subpackage; never top-level, kept out by contract)
    "DeviceAdapter",
    "QuestAdapter",
    "RobotAdapter",
]
# Note on ``extensions``: it is a repo-root data directory (registry.json +
# registry.schema.json), not a Python submodule, and has no top-level exports.
# Its x-<vendor>. convention lives in ``schema`` via VENDOR_EXTENSION_PREFIX
# (a main-path name, still exported) + JSON Schema patternProperties.


def test_frozen_names_not_exported_at_top_level():
    """No frozen name leaks at the package top level."""
    leaked = [name for name in FROZEN_NAMES if hasattr(mc, name)]
    assert leaked == [], f"frozen names leaked to top level: {leaked}"

    # VENDOR_EXTENSION_PREFIX belongs to the schema group (main path) and MUST
    # stay exported — it is not an ``extensions`` freeze victim.
    assert hasattr(mc, "VENDOR_EXTENSION_PREFIX"), "VENDOR_EXTENSION_PREFIX must stay exported"


# ── Frozen submodules remain importable via their full path ──────────────────
# The five importable frozen submodules. ``extensions/`` is a data directory,
# not a submodule, so it is not in this list (see note above).
FROZEN_SUBMODULES = [
    "mnesis_canonical.isaac",
    "mnesis_canonical.migrate",
    "mnesis_canonical.skeleton_registry",
    "mnesis_canonical.objects_jsonl",
    "mnesis_canonical.sdk",
]


def test_frozen_modules_still_importable():
    """Frozen submodules are not deleted — still importable via submodule path."""
    for modname in FROZEN_SUBMODULES:
        importlib.import_module(modname)
