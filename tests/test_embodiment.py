"""Tests for the Embodiment Registry (embodiments/<id>.json + schema validation)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mnesis_canonical.embodiment_check import (
    _discover_embodiments,
    load_embodiment,
    load_schema,
    validate_embodiment,
    validate_embodiment_jsonschema,
)

_EMBODIMENTS_DIR = Path(__file__).resolve().parent.parent / "embodiments"


def test_all_embodiments_exist():
    """There must be at least 5 embodiment files (the initial set)."""
    paths = _discover_embodiments()
    assert len(paths) >= 5, f"Expected >=5 embodiments, found {len(paths)}"


def test_expected_embodiments_present():
    """The five required embodiments must be present."""
    ids = {p.stem for p in _discover_embodiments()}
    required = {"ego_human", "alohamini", "so_arm101", "airbot_play", "dual_airbot_play"}
    missing = required - ids
    assert not missing, f"Missing required embodiments: {missing}"


def test_schema_loads():
    """The embodiment JSON Schema must load correctly."""
    schema = load_schema()
    assert schema["$schema"].endswith("2020-12/schema")
    required = {"id", "display_name", "arms", "dof_per_arm", "joint_names",
                "joint_limits", "gripper_range", "base_frame", "assets", "teleop"}
    assert set(schema["required"]) == required


def test_each_embodiment_passes_schema():
    """Every embodiment file must pass the JSON Schema validation."""
    pytest.importorskip("jsonschema")
    schema = load_schema()
    for path in _discover_embodiments():
        data = load_embodiment(path)
        errs = validate_embodiment_jsonschema(data, schema)
        assert not errs, f"{path.name}: {errs}"


def test_each_embodiment_passes_python_checks():
    """Every embodiment file must pass the pure-Python checks."""
    for path in _discover_embodiments():
        data = load_embodiment(path)
        errs = validate_embodiment(data)
        assert not errs, f"{path.name}: {errs}"


def test_embodiment_id_matches_filename():
    """The id field must match the filename stem."""
    for path in _discover_embodiments():
        data = load_embodiment(path)
        assert data["id"] == path.stem, f"{path.name}: id '{data['id']}' != '{path.stem}'"


def test_dual_airbot_play_has_two_arms():
    """dual_airbot_play must have arms=2."""
    path = _EMBODIMENTS_DIR / "dual_airbot_play.json"
    data = load_embodiment(path)
    assert data["arms"] == 2


def test_single_arm_embodiments():
    """Single-arm embodiments must have arms=1."""
    for name in ("so_arm101", "airbot_play"):
        path = _EMBODIMENTS_DIR / f"{name}.json"
        data = load_embodiment(path)
        assert data["arms"] == 1, f"{name} should be single-arm"


def test_joint_limits_length_matches_joint_names():
    """joint_limits.min and .max must match joint_names length."""
    for path in _discover_embodiments():
        data = load_embodiment(path)
        n = len(data["joint_names"])
        assert len(data["joint_limits"]["min"]) == n, f"{path.name}: min length mismatch"
        assert len(data["joint_limits"]["max"]) == n, f"{path.name}: max length mismatch"


def test_arm_parity_dual_embodiments():
    """Dual-arm embodiments must have even joint count."""
    for path in _discover_embodiments():
        data = load_embodiment(path)
        if data["arms"] > 1:
            assert len(data["joint_names"]) % data["arms"] == 0, (
                f"{path.name}: {len(data['joint_names'])} joints"
                f" not divisible by {data['arms']} arms"
            )


def test_workspace_box_shape():
    """workspace_box must be [[x_min, y_min, z_min], [x_max, y_max, z_max]]."""
    for path in _discover_embodiments():
        data = load_embodiment(path)
        box = data["teleop"]["workspace_box"]
        assert len(box) == 2
        assert len(box[0]) == 3
        assert len(box[1]) == 3
        # min must be <= max for each axis
        for i in range(3):
            assert box[0][i] <= box[1][i], (
                f"{path.name}: workspace_box[{i}] min > max ({box[0][i]} > {box[1][i]})"
            )


def test_assets_have_required_keys():
    """Every embodiment must have all four asset keys."""
    for path in _discover_embodiments():
        data = load_embodiment(path)
        for key in ("urdf", "mjcf", "glb", "skeleton"):
            assert key in data["assets"], f"{path.name}: missing asset key '{key}'"


def test_teleop_has_required_keys():
    """Every embodiment must have teleop.default_pos_scale and workspace_box."""
    for path in _discover_embodiments():
        data = load_embodiment(path)
        assert "default_pos_scale" in data["teleop"]
        assert "workspace_box" in data["teleop"]
        assert data["teleop"]["default_pos_scale"] > 0


def test_ruff_clean_format():
    """Embodiment JSON files should be valid JSON (smoke check)."""
    for path in _discover_embodiments():
        raw = path.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)
        assert parsed["id"] == path.stem