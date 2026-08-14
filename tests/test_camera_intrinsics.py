"""Conformance tests for camera_intrinsics (C9, v1, additive).

Camera intrinsics live in the embodiment registry's ``capture.cameras[].intrinsics``
field, not in the per-frame schema.  These tests verify that:

1. The embodiment JSON Schema accepts valid intrinsics blocks.
2. The embodiment JSON Schema rejects invalid intrinsics (missing model, bad model enum).
3. The ``CAMERA_MODELS`` constant in ``schema.py`` matches the JSON Schema enum.
4. The package-embodied schema matches the root schema (already covered by
   ``test_embodiment.py``'s ``test_package_data_sync_with_root``).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mnesis_canonical import CAMERA_MODELS
from mnesis_canonical.embodiment_check import load_schema, validate_embodiment_jsonschema

_EMBODIMENTS_DIR = Path(__file__).resolve().parent.parent / "embodiments"


# ── Helpers ──────────────────────────────────────────────────────────────────────


def _make_embodiment_with_intrinsics(**overrides) -> dict:
    """Return a minimal embodiment dict that includes camera intrinsics.

    Based on the real ``airbot_play.json`` shape, with the capture section
    extended to include intrinsics.
    """
    base = {
        "id": "test_cam",
        "display_name": "Test Camera",
        "arms": 1,
        "dof_per_arm": 6,
        "joint_names": ["j1", "j2", "j3", "j4", "j5", "j6"],
        "joint_limits": {
            "min": [-3.14, -3.14, -3.14, -3.14, -3.14, -3.14],
            "max": [3.14, 3.14, 3.14, 3.14, 3.14, 3.14],
        },
        "gripper_range": [0.0, 1.0],
        "base_frame": "base",
        "assets": {"urdf": "", "mjcf": "", "glb": "", "skeleton": ""},
        "teleop": {
            "default_pos_scale": 0.3,
            "workspace_box": [[-0.5, -0.5, 0.0], [0.5, 0.5, 1.0]],
        },
        "capture": {
            "default_fps": 30,
            "cameras": [
                {
                    "name": "front",
                    "resolution": [1920, 1200],
                    "intrinsics": {
                        "model": "kannala_brandt",
                        "width": 1920,
                        "height": 1200,
                        "fx": 950.0,
                        "fy": 945.0,
                        "cx": 960.0,
                        "cy": 600.0,
                        "distortion": [0.02, -0.01, 0.005, 0.001],
                    },
                },
            ],
        },
    }
    # Apply overrides to the first camera's intrinsics
    if "intrinsics" in overrides:
        base["capture"]["cameras"][0]["intrinsics"] = overrides["intrinsics"]
    return base


# ── Schema-level tests ───────────────────────────────────────────────────────────


def test_camera_models_enum():
    """CAMERA_MODELS must contain the four expected values."""
    assert CAMERA_MODELS == ("pinhole", "pinhole_radtan", "kannala_brandt", "double_sphere")


def test_schema_enum_matches_python_constant():
    """The JSON Schema enum for model must match the Python CAMERA_MODELS constant."""
    schema = load_schema()
    cameras_items = schema["properties"]["capture"]["properties"]["cameras"]["items"]
    intrinsics = cameras_items["properties"]["intrinsics"]
    model_prop = intrinsics["properties"]["model"]
    schema_enum = set(model_prop["enum"])
    assert schema_enum == set(CAMERA_MODELS), (
        f"Schema enum {schema_enum} != Python CAMERA_MODELS {set(CAMERA_MODELS)}"
    )


def test_intrinsics_required_fields():
    """The intrinsics schema must require model, width, height, fx, fy, cx, cy."""
    schema = load_schema()
    cameras_items = schema["properties"]["capture"]["properties"]["cameras"]["items"]
    intrinsics = cameras_items["properties"]["intrinsics"]
    required = set(intrinsics["required"])
    expected = {"model", "width", "height", "fx", "fy", "cx", "cy"}
    assert required == expected, f"intrinsics required {required} != expected {expected}"


# ── Validation tests ─────────────────────────────────────────────────────────────


def test_valid_intrinsics_passes_schema():
    """A valid embodiment with kannala_brandt intrinsics must pass schema validation."""
    pytest.importorskip("jsonschema")
    schema = load_schema()
    embodiment = _make_embodiment_with_intrinsics()
    errs = validate_embodiment_jsonschema(embodiment, schema)
    assert not errs, f"Unexpected errors: {errs}"


def test_valid_pinhole_intrinsics_passes():
    """pinhole model (no distortion) must pass."""
    pytest.importorskip("jsonschema")
    schema = load_schema()
    embodiment = _make_embodiment_with_intrinsics(
        intrinsics={
            "model": "pinhole",
            "width": 1920,
            "height": 1200,
            "fx": 1000.0,
            "fy": 1000.0,
            "cx": 960.0,
            "cy": 600.0,
        }
    )
    errs = validate_embodiment_jsonschema(embodiment, schema)
    assert not errs, f"pinhole intrinsics should pass: {errs}"


def test_valid_pinhole_radtan_passes():
    """pinhole_radtan model with 5-element distortion must pass."""
    pytest.importorskip("jsonschema")
    schema = load_schema()
    embodiment = _make_embodiment_with_intrinsics(
        intrinsics={
            "model": "pinhole_radtan",
            "width": 640,
            "height": 480,
            "fx": 320.5,
            "fy": 319.8,
            "cx": 320.0,
            "cy": 240.0,
            "distortion": [0.05, -0.02, 0.001, 0.003, 0.0],
        }
    )
    errs = validate_embodiment_jsonschema(embodiment, schema)
    assert not errs, f"pinhole_radtan intrinsics should pass: {errs}"


def test_valid_double_sphere_passes():
    """double_sphere model with 6-element distortion must pass."""
    pytest.importorskip("jsonschema")
    schema = load_schema()
    embodiment = _make_embodiment_with_intrinsics(
        intrinsics={
            "model": "double_sphere",
            "width": 1920,
            "height": 1200,
            "fx": 950.0,
            "fy": 945.0,
            "cx": 960.0,
            "cy": 600.0,
            "distortion": [0.5, 0.3, 0.02, -0.01, 0.005, 0.001],
        }
    )
    errs = validate_embodiment_jsonschema(embodiment, schema)
    assert not errs, f"double_sphere intrinsics should pass: {errs}"


def test_missing_model_rejected():
    """intrinsics without model must be rejected by schema."""
    pytest.importorskip("jsonschema")
    schema = load_schema()
    embodiment = _make_embodiment_with_intrinsics(
        intrinsics={
            "width": 1920,
            "height": 1200,
            "fx": 950.0,
            "fy": 945.0,
            "cx": 960.0,
            "cy": 600.0,
        }
    )
    errs = validate_embodiment_jsonschema(embodiment, schema)
    assert any("model" in e for e in errs), (
        f"Expected 'model' required error, got: {errs}"
    )


def test_unknown_model_rejected():
    """An unrecognized model string must be rejected."""
    pytest.importorskip("jsonschema")
    schema = load_schema()
    embodiment = _make_embodiment_with_intrinsics(
        intrinsics={
            "model": "unknown_model",
            "width": 1920,
            "height": 1200,
            "fx": 950.0,
            "fy": 945.0,
            "cx": 960.0,
            "cy": 600.0,
        }
    )
    errs = validate_embodiment_jsonschema(embodiment, schema)
    assert any("unknown_model" in e for e in errs), (
        f"Expected unknown model rejection, got: {errs}"
    )


def test_missing_width_rejected():
    """intrinsics without width must be rejected."""
    pytest.importorskip("jsonschema")
    schema = load_schema()
    embodiment = _make_embodiment_with_intrinsics(
        intrinsics={
            "model": "pinhole",
            "height": 1200,
            "fx": 950.0,
            "fy": 945.0,
            "cx": 960.0,
            "cy": 600.0,
        }
    )
    errs = validate_embodiment_jsonschema(embodiment, schema)
    assert any("width" in e for e in errs), (
        f"Expected 'width' required error, got: {errs}"
    )


def test_embodiment_without_intrinsics_still_valid():
    """An embodiment entry without the intrinsics field must still pass (additive)."""
    pytest.importorskip("jsonschema")
    schema = load_schema()
    # Strip intrinsics from the camera entry
    embodiment = _make_embodiment_with_intrinsics()
    del embodiment["capture"]["cameras"][0]["intrinsics"]
    errs = validate_embodiment_jsonschema(embodiment, schema)
    assert not errs, f"Embodiment without intrinsics should still pass: {errs}"


def test_embodiment_without_capture_still_valid():
    """An embodiment entry without the entire capture section must still pass (additive)."""
    pytest.importorskip("jsonschema")
    schema = load_schema()
    embodiment = _make_embodiment_with_intrinsics()
    del embodiment["capture"]
    errs = validate_embodiment_jsonschema(embodiment, schema)
    assert not errs, f"Embodiment without capture should still pass: {errs}"


def test_negative_width_rejected():
    """Negative width must be rejected (minimum 1)."""
    pytest.importorskip("jsonschema")
    schema = load_schema()
    embodiment = _make_embodiment_with_intrinsics(
        intrinsics={
            "model": "pinhole",
            "width": -1,
            "height": 1200,
            "fx": 950.0,
            "fy": 945.0,
            "cx": 960.0,
            "cy": 600.0,
        }
    )
    errs = validate_embodiment_jsonschema(embodiment, schema)
    assert any("width" in e for e in errs), (
        f"Expected negative width error, got: {errs}"
    )


def test_zero_fx_rejected():
    """Zero focal length must be rejected (exclusiveMinimum 0)."""
    pytest.importorskip("jsonschema")
    schema = load_schema()
    embodiment = _make_embodiment_with_intrinsics(
        intrinsics={
            "model": "pinhole",
            "width": 1920,
            "height": 1200,
            "fx": 0,
            "fy": 945.0,
            "cx": 960.0,
            "cy": 600.0,
        }
    )
    errs = validate_embodiment_jsonschema(embodiment, schema)
    assert any("fx" in e for e in errs), (
        f"Expected zero fx error, got: {errs}"
    )


# ── Real embodiment test ─────────────────────────────────────────────────────────


def test_real_embodiments_without_intrinsics_still_pass():
    """All five real embodiment files must still pass validation (they have no intrinsics)."""
    pytest.importorskip("jsonschema")
    schema = load_schema()
    from mnesis_canonical.embodiment_check import _discover_embodiments, load_embodiment
    for path in _discover_embodiments():
        data = load_embodiment(path)
        errs = validate_embodiment_jsonschema(data, schema)
        assert not errs, f"{path.name}: {errs}"