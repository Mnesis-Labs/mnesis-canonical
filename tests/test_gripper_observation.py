"""Conformance tests for the observation-side gripper channel (additive).

The gripper *observation* is a continuous **closedness** scalar in [0, 1] carried
as an optional first-class field: ``observation.gripper`` (single/main) and
``observation.gripper.{left,right}`` (bimanual robot_v2). Direction is identical
to ``action.gripper`` and to the C3 xr_bridge wire field ``arms[].gripper``:
**0.0 = fully open, 1.0 = fully closed**. All keys are optional and additive —
frames without them validate unchanged.

The action-side field ``action.gripper`` is covered separately in
``tests/test_gripper.py``; this file adds the observation side plus a same-frame
co-existence case proving the two fields share one direction.
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest

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
    f = good_frame()
    assert "observation.gripper" not in f
    assert validate_frame(f) == []


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


# --- direction: 0 = open, 1 = closed (same as action.gripper) ----------------

def test_action_and_observation_gripper_same_direction(good_frame):
    """Same frame carrying both action.gripper and observation.gripper at the
    same value must validate, and the two fields share one direction:
    0.3 means the same "mostly open" state for both (0.0 = open, 1.0 = closed).
    """
    f = good_frame()
    f["action.gripper"] = 0.3
    f["observation.gripper"] = 0.3
    assert validate_frame(f) == []

    # Round-trips through the dataclass preserve both fields as the same value.
    frame = CanonicalFrame.from_dict(f)
    assert frame.action_gripper == 0.3
    assert frame.gripper == 0.3
    out = frame.to_dict()
    assert out["action.gripper"] == out["observation.gripper"] == 0.3

    # 0.3 is on the open half of the shared [0=open, 1=closed] closedness scale.
    assert out["observation.gripper"] < 0.5  # "偏开" — mostly open, both fields


def test_boundary_semantics_open_and_closed(good_frame):
    """Endpoints: 0.0 = fully open, 1.0 = fully closed — both accepted."""
    for val in (GRIPPER_MIN, GRIPPER_MAX):
        f = good_frame()
        f["observation.gripper"] = val
        f["action.gripper"] = val
        assert validate_frame(f) == []


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
