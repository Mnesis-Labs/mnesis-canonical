"""Conformance tests for the embodiment `capture` section + `capture_profiles`
presets (issue #41, additive/optional — v0.5).

These are *additive*: the `capture` block and `capture_profiles` are optional, so
embodiments without them must keep validating, and every existing test is
unchanged. SO-ARM101 and AIRBOT Play carry filled-in real values.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mnesis_canonical.embodiment_check import (
    _discover_embodiments,
    load_embodiment,
    load_schema,
    validate_embodiment_jsonschema,
)

_ROOT = Path(__file__).resolve().parent.parent
_EMBODIMENTS_DIR = _ROOT / "embodiments"
_PKG_EMBODIMENTS_DIR = _ROOT / "mnesis_canonical" / "embodiments"

_DEMO_MODES = {"kinesthetic", "leader_follower", "teleop_only"}
_GRIPPER_MODES = {"continuous", "binary", "none"}


# ── capture is additive / optional ──────────────────────────────────────────────


def test_capture_is_optional_in_schema():
    """`capture`/`capture_profiles` must NOT be in the schema's required list."""
    schema = load_schema()
    assert "capture" not in schema["required"]
    assert "capture_profiles" not in schema["required"]
    # But they must be declared as known properties.
    assert "capture" in schema["properties"]
    assert "capture_profiles" in schema["properties"]


def test_embodiments_without_capture_still_validate():
    """Embodiments that omit `capture` must keep passing schema validation."""
    pytest.importorskip("jsonschema")
    schema = load_schema()
    for path in _discover_embodiments():
        data = load_embodiment(path)
        if "capture" not in data:
            errs = validate_embodiment_jsonschema(data, schema)
            assert not errs, f"{path.name}: {errs}"


def test_all_embodiments_pass_schema_with_capture():
    """Every embodiment file (with or without capture) validates."""
    pytest.importorskip("jsonschema")
    schema = load_schema()
    for path in _discover_embodiments():
        data = load_embodiment(path)
        errs = validate_embodiment_jsonschema(data, schema)
        assert not errs, f"{path.name}: {errs}"


# ── Two machines carry filled-in real values ────────────────────────────────────


@pytest.mark.parametrize("eid", ["so_arm101", "airbot_play"])
def test_machine_has_capture_section(eid):
    data = load_embodiment(_EMBODIMENTS_DIR / f"{eid}.json")
    cap = data["capture"]
    assert cap["default_fps"] > 0
    assert cap["max_duration_s"] > 0
    assert len(cap["cameras"]) >= 1
    for cam in cap["cameras"]:
        assert cam["name"]
        assert len(cam["resolution"]) == 2
        assert all(px >= 1 for px in cam["resolution"])
    assert cap["gripper_capture"]["mode"] in _GRIPPER_MODES
    assert set(cap["demonstration_modes"]) <= _DEMO_MODES
    assert cap["demonstration_modes"]  # non-empty
    assert isinstance(cap["calibration"]["hand_eye_required"], bool)


def test_so_arm101_is_leader_follower():
    """SO-ARM101 teaches via leader-follower (per issue #41 truth)."""
    data = load_embodiment(_EMBODIMENTS_DIR / "so_arm101.json")
    assert data["capture"]["demonstration_modes"] == ["leader_follower"]


def test_airbot_play_is_kinesthetic():
    """AIRBOT Play supports gravity-comp kinesthetic drag teaching (issue #41)."""
    data = load_embodiment(_EMBODIMENTS_DIR / "airbot_play.json")
    assert data["capture"]["demonstration_modes"] == ["kinesthetic"]


# ── capture_profiles presets ────────────────────────────────────────────────────


@pytest.mark.parametrize("eid", ["so_arm101", "airbot_play"])
def test_capture_profiles_reference_declared_cameras(eid):
    """Each preset's cameras must be a subset of the embodiment's capture cameras."""
    data = load_embodiment(_EMBODIMENTS_DIR / f"{eid}.json")
    declared = {c["name"] for c in data["capture"]["cameras"]}
    profiles = data["capture_profiles"]
    assert profiles, f"{eid}: expected at least one capture profile"
    names = [p["name"] for p in profiles]
    assert len(names) == len(set(names)), f"{eid}: duplicate preset names"
    for p in profiles:
        assert p["name"]
        for cam in p.get("cameras", []):
            assert cam in declared, f"{eid}: preset camera '{cam}' not in capture.cameras"


def test_capture_profile_annotation_template_exists():
    """A preset's annotation_template should point at a real taxonomy file."""
    for eid in ("so_arm101", "airbot_play"):
        data = load_embodiment(_EMBODIMENTS_DIR / f"{eid}.json")
        for p in data["capture_profiles"]:
            tmpl = p.get("annotation_template")
            if tmpl:
                assert (_ROOT / "taxonomies" / f"{tmpl}.json").exists(), (
                    f"{eid}: annotation_template '{tmpl}' has no taxonomies/{tmpl}.json"
                )


# ── root ↔ package sync for the changed schema + machine files ───────────────────


def test_schema_synced_root_and_package():
    """The schema (with the new capture block) must match byte-for-byte."""
    root = (_EMBODIMENTS_DIR / "embodiment.schema.json").read_bytes()
    pkg = (_PKG_EMBODIMENTS_DIR / "embodiment.schema.json").read_bytes()
    assert root == pkg, "embodiment.schema.json differs between root and package"


def test_capture_present_in_package_copies():
    """Package-data copies must also carry the capture section."""
    for eid in ("so_arm101", "airbot_play"):
        data = load_embodiment(_PKG_EMBODIMENTS_DIR / f"{eid}.json")
        assert "capture" in data
        assert "capture_profiles" in data
