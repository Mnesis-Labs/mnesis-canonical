"""Tests for the optional additive `action.gripper` field (v0.4+).

Semantics: normalized float in [0.0, 1.0] (0.0 = fully open, 1.0 = fully closed).
Additive-only — absence means "source provides no gripper info" (NOT 0.0), and
existing data without the field must validate unchanged.
"""
from __future__ import annotations

import math
import pytest
from pathlib import Path

from mnesis_canonical import (
    GRIPPER_KEYS,
    GRIPPER_MAX,
    GRIPPER_MIN,
    CanonicalFrame,
    load_json_schema,
    read_jsonl,
    validate_frame,
    validate_frame_jsonschema,
    validate_frames,
)

# ── Regression: additive-only, old data unaffected ──────────────────────────────


def test_frame_without_gripper_validates(good_frame):
    """The core additive guarantee: no action.gripper key = still valid."""
    f = good_frame()
    assert "action.gripper" not in f
    assert validate_frame(f) == []


def test_robot_v2_frame_without_gripper_validates():
    """robot_v2 frames without the field are unaffected too."""
    f = {
        "index": 0, "episode_index": 0, "task_index": 0, "frame_index": 0,
        "t_ns": 1_000_000, "t_hw_ns": 1_000_000_000,
        "timestamp": "2026-07-21T00:00:00.000Z",
        "head_pose_SE3": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        "observation.state": [0.0] * 14,
        "observation.images.wrist_left": "",
        "action": [0.0] * 14,
        "spatial_anchor_id": None,
        "source.device": "robot", "source.modality": "robot_replay",
        "tracking_state": "TRACKING",
        "profile": "robot_v2",
    }
    assert validate_frame(f) == []


# ── Present + in range ──────────────────────────────────────────────────────────


def test_gripper_boundary_values_validate(good_frame):
    """Closed interval: 0.0 and 1.0 are both valid."""
    for g in (0.0, 0.5, 1.0):
        f = good_frame()
        f["action.gripper"] = g
        assert validate_frame(f) == [], f"gripper={g} should validate"


def test_gripper_int_value_validates(good_frame):
    """An int 0 or 1 is an acceptable number in range."""
    f = good_frame()
    f["action.gripper"] = 1
    assert validate_frame(f) == []


def test_gripper_on_robot_v2_validates():
    """action.gripper is profile-independent (works on robot_v2 too)."""
    f = {
        "index": 0, "episode_index": 0, "task_index": 0, "frame_index": 0,
        "t_ns": 1_000_000, "t_hw_ns": 1_000_000_000,
        "timestamp": "2026-07-21T00:00:00.000Z",
        "head_pose_SE3": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        "observation.state": [0.0] * 7,
        "observation.images.wrist_left": "",
        "action": [0.0] * 6,
        "spatial_anchor_id": None,
        "source.device": "robot", "source.modality": "robot_replay",
        "tracking_state": "TRACKING",
        "profile": "robot_v2",
        "action.gripper": 0.72,
    }
    assert validate_frame(f) == []


# ── Out of range / bad type → clear error ───────────────────────────────────────


def test_gripper_below_zero_rejected(good_frame):
    f = good_frame()
    f["action.gripper"] = -0.1
    errs = validate_frame(f)
    assert any("action.gripper" in e and "[0.0, 1.0]" in e for e in errs), errs


def test_gripper_above_one_rejected(good_frame):
    f = good_frame()
    f["action.gripper"] = 1.5
    errs = validate_frame(f)
    assert any("action.gripper" in e and "[0.0, 1.0]" in e for e in errs), errs


def test_gripper_non_numeric_rejected(good_frame):
    f = good_frame()
    f["action.gripper"] = "closed"
    errs = validate_frame(f)
    assert any("action.gripper" in e for e in errs), errs


def test_gripper_bool_rejected(good_frame):
    """bool is not an acceptable gripper value even though bool subclasses int."""
    f = good_frame()
    f["action.gripper"] = True
    errs = validate_frame(f)
    assert any("action.gripper" in e for e in errs), errs


def test_gripper_nan_rejected(good_frame):
    f = good_frame()
    f["action.gripper"] = math.nan
    errs = validate_frame(f)
    assert any("action.gripper" in e for e in errs), errs


def test_gripper_out_of_range_flagged_by_validate_frames(good_frame):
    """Episode-level validation surfaces the per-frame error."""
    f = good_frame()
    f["action.gripper"] = 2.0
    report = validate_frames([f])
    assert not report.ok
    assert any("action.gripper" in e for _, e in report.errors)


# ── Round-trip: None absent, value present ──────────────────────────────────────


def test_to_dict_omits_gripper_when_none(good_frame):
    """None gripper must not appear in the wire dict."""
    base = good_frame()
    frame = CanonicalFrame.from_dict(base)
    assert frame.action_gripper is None
    assert "action.gripper" not in frame.to_dict()


def test_round_trip_preserves_gripper(good_frame):
    base = good_frame()
    base["action.gripper"] = 0.42
    frame = CanonicalFrame.from_dict(base)
    assert frame.action_gripper == 0.42
    out = frame.to_dict()
    assert out["action.gripper"] == 0.42
    # Full round-trip is stable and valid.
    assert validate_frame(out) == []
    assert CanonicalFrame.from_dict(out).action_gripper == 0.42


# === C8 observation.gripper tests (from D-18 contracts vNext) ===

EXAMPLE_GRIPPER = (
    Path(__file__).resolve().parent.parent / "examples" / "episode_gripper" / "data.jsonl"
)


def _robot_v2_frame() -> dict:
    """A minimal valid robot_v2 frame (variable vectors, one camera)."""
    return {
        "index": 0, "episode_index": 6, "task_index": 0, "frame_index": 0,
        "t_ns": 1_000_000, "t_hw_ns": 6_000_000_000,
        "timestamp": "2026-07-22T00:30:00.000Z",
        "head_pose_SE3": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        "observation.state": [0.0, -1.7, 1.57, 0.0, 0.0, 0.2],
        "observation.images.head": "frames/000000.jpg",
        "action": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "spatial_anchor_id": None,
        "source.device": "robot", "source.modality": "teleop",
        "tracking_state": "TRACKING",
        "profile": "robot_v2",
    }


# --- constants ---------------------------------------------------------------

def test_gripper_constants_exported():
    assert GRIPPER_KEYS == (
        "observation.gripper",
        "observation.gripper.left",
        "observation.gripper.right",
    )
    assert GRIPPER_MIN == 0.0
    assert GRIPPER_MAX == 1.0


# --- additive: absence is unchanged ------------------------------------------

def test_frame_without_gripper_still_valid(good_frame):
    """No gripper key present → validates exactly as before (additive-only)."""
    assert validate_frame(good_frame()) == []


# --- single / main gripper ---------------------------------------------------

@pytest.mark.parametrize("val", [0.0, 0.2, 0.5, 1.0])
def test_gripper_in_range_accepted(good_frame, val):
    f = good_frame()
    f["observation.gripper"] = val
    assert validate_frame(f) == []


@pytest.mark.parametrize("val", [-0.01, 1.01, 2.0, -1.0])
def test_gripper_out_of_range_rejected(good_frame, val):
    f = good_frame()
    f["observation.gripper"] = val
    errs = validate_frame(f)
    assert any("observation.gripper" in e and "0.0, 1.0" in e for e in errs)


@pytest.mark.parametrize("val", ["0.5", True, None, [0.5]])
def test_gripper_wrong_type_rejected(good_frame, val):
    f = good_frame()
    f["observation.gripper"] = val
    errs = validate_frame(f)
    assert any("observation.gripper" in e for e in errs)


@pytest.mark.parametrize("val", [math.nan, math.inf, -math.inf])
def test_gripper_non_finite_rejected(good_frame, val):
    f = good_frame()
    f["observation.gripper"] = val
    errs = validate_frame(f)
    assert any("observation.gripper" in e and "finite" in e for e in errs)


# --- bimanual left / right grippers ------------------------------------------

def test_gripper_left_right_accepted():
    f = _robot_v2_frame()
    f["observation.gripper.left"] = 0.3
    f["observation.gripper.right"] = 0.7
    assert validate_frame(f) == []


def test_gripper_left_out_of_range_rejected():
    f = _robot_v2_frame()
    f["observation.gripper.left"] = 1.5
    errs = validate_frame(f)
    assert any("observation.gripper.left" in e for e in errs)


def test_gripper_right_out_of_range_rejected():
    f = _robot_v2_frame()
    f["observation.gripper.right"] = -0.2
    errs = validate_frame(f)
    assert any("observation.gripper.right" in e for e in errs)


# --- dataclass roundtrip -----------------------------------------------------

def test_dataclass_roundtrip_with_gripper(good_frame):
    d = good_frame()
    d["observation.gripper"] = 0.2
    d["observation.gripper.left"] = 0.3
    d["observation.gripper.right"] = 0.7
    assert CanonicalFrame.from_dict(d).to_dict() == d


def test_dataclass_omits_gripper_when_absent(good_frame):
    d = good_frame()
    round_tripped = CanonicalFrame.from_dict(d).to_dict()
    assert "observation.gripper" not in round_tripped


# --- JSON Schema -------------------------------------------------------------

def test_json_schema_declares_gripper_properties():
    props = load_json_schema()["properties"]
    for key in GRIPPER_KEYS:
        assert key in props, f"{key} missing from JSON Schema"
        assert props[key]["type"] == "number"
        assert props[key]["minimum"] == 0.0
        assert props[key]["maximum"] == 1.0


def test_jsonschema_backend_rejects_out_of_range_gripper(good_frame):
    pytest.importorskip("jsonschema")
    f = good_frame()
    f["observation.gripper"] = 1.5
    assert validate_frame_jsonschema(f)  # non-empty error list


def test_jsonschema_backend_accepts_valid_gripper(good_frame):
    pytest.importorskip("jsonschema")
    f = good_frame()
    f["observation.gripper"] = 0.5
    assert validate_frame_jsonschema(f) == []


# --- example episode ---------------------------------------------------------

def test_example_gripper_episode_validates():
    report = validate_frames(read_jsonl(EXAMPLE_GRIPPER), strict_vocab=True)
    assert report.ok, report.errors
    assert report.total == 2 and report.valid == 2


def test_example_gripper_episode_carries_gripper():
    frames = read_jsonl(EXAMPLE_GRIPPER)
    assert all("observation.gripper" in f for f in frames)
    assert all(GRIPPER_MIN <= f["observation.gripper"] <= GRIPPER_MAX for f in frames)