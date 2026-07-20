"""Tests for the v0.2 profile mechanism — ego_v1 (default) + robot_v2."""
from __future__ import annotations

from pathlib import Path

from mnesis_canonical import (
    read_jsonl,
    required_keys_for_profile,
    validate_frame,
    validate_frames,
)

DUAL_AIRBOT = (
    Path(__file__).resolve().parent.parent / "examples" / "episode_dual_airbot" / "data.jsonl"
)


# ── Regression: v0.1 frames without profile still validate ──────────────────────


def test_v0_1_frame_without_profile_validates(good_frame):
    """A v0.1 frame (no profile) must pass validation unchanged."""
    assert validate_frame(good_frame()) == []


def test_v0_1_frame_with_explicit_ego_v1_validates(good_frame):
    """Explicit profile='ego_v1' is equivalent to absent profile."""
    f = good_frame()
    f["profile"] = "ego_v1"
    assert validate_frame(f) == []


def test_v0_1_frame_missing_observation_images_ego_still_fails(good_frame):
    """ego_v1 (explicit or implicit) still requires observation.images.ego."""
    f = good_frame()
    del f["observation.images.ego"]
    errs = validate_frame(f)
    assert any("observation.images.ego" in e for e in errs)


# ── robot_v2 profile ────────────────────────────────────────────────────────────


def test_robot_v2_variable_state_validates():
    """robot_v2 allows variable-length observation.state (e.g. 14 for dual arm)."""
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
        "embodiment_id": "dual_airbot_v1",
    }
    assert validate_frame(f) == []


def test_robot_v2_variable_action_validates():
    """robot_v2 allows variable-length action."""
    f = {
        "index": 0, "episode_index": 0, "task_index": 0, "frame_index": 0,
        "t_ns": 1_000_000, "t_hw_ns": 1_000_000_000,
        "timestamp": "2026-07-21T00:00:00.000Z",
        "head_pose_SE3": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        "observation.state": [0.0] * 7,
        "observation.images.wrist_left": "",
        "action": [0.0] * 8,
        "spatial_anchor_id": None,
        "source.device": "robot", "source.modality": "robot_replay",
        "tracking_state": "TRACKING",
        "profile": "robot_v2",
    }
    assert validate_frame(f) == []


def test_robot_v2_does_not_require_ego_camera():
    """robot_v2 does not require observation.images.ego."""
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
    }
    assert validate_frame(f) == []


def test_robot_v2_requires_at_least_one_camera():
    """robot_v2 must have at least one observation.images.<cam> key."""
    f = {
        "index": 0, "episode_index": 0, "task_index": 0, "frame_index": 0,
        "t_ns": 1_000_000, "t_hw_ns": 1_000_000_000,
        "timestamp": "2026-07-21T00:00:00.000Z",
        "head_pose_SE3": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        "observation.state": [0.0] * 7,
        "action": [0.0] * 6,
        "spatial_anchor_id": None,
        "source.device": "robot", "source.modality": "robot_replay",
        "tracking_state": "TRACKING",
        "profile": "robot_v2",
    }
    errs = validate_frame(f)
    assert any("observation.images" in e for e in errs)


def test_robot_v2_multiple_cameras_accepted():
    """robot_v2 can have multiple camera keys (wrist_left, wrist_right, head, etc.)."""
    f = {
        "index": 0, "episode_index": 0, "task_index": 0, "frame_index": 0,
        "t_ns": 1_000_000, "t_hw_ns": 1_000_000_000,
        "timestamp": "2026-07-21T00:00:00.000Z",
        "head_pose_SE3": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        "observation.state": [0.0] * 7,
        "observation.images.wrist_left": "",
        "observation.images.wrist_right": "",
        "observation.images.head": "",
        "observation.images.quest_cast": "",
        "action": [0.0] * 6,
        "spatial_anchor_id": None,
        "source.device": "robot", "source.modality": "robot_replay",
        "tracking_state": "TRACKING",
        "profile": "robot_v2",
    }
    assert validate_frame(f) == []


def test_robot_v2_eef_pose_left_validates():
    """robot_v2 optional eef_pose.left must be float[7]."""
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
        "observation.eef_pose.left": [0.5, 0.3, 0.2, 0.0, 0.0, 0.0, 1.0],
    }
    assert validate_frame(f) == []


def test_robot_v2_eef_pose_right_validates():
    f = {
        "index": 0, "episode_index": 0, "task_index": 0, "frame_index": 0,
        "t_ns": 1_000_000, "t_hw_ns": 1_000_000_000,
        "timestamp": "2026-07-21T00:00:00.000Z",
        "head_pose_SE3": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        "observation.state": [0.0] * 7,
        "observation.images.wrist_right": "",
        "action": [0.0] * 6,
        "spatial_anchor_id": None,
        "source.device": "robot", "source.modality": "robot_replay",
        "tracking_state": "TRACKING",
        "profile": "robot_v2",
        "observation.eef_pose.right": [0.5, -0.3, 0.2, 0.0, 0.0, 0.0, 1.0],
    }
    assert validate_frame(f) == []


def test_robot_v2_eef_pose_wrong_length_rejected():
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
        "observation.eef_pose.left": [0.5, 0.3, 0.2],  # should be length 7
    }
    errs = validate_frame(f)
    assert any("eef_pose.left" in e for e in errs)


# ── Edge cases ──────────────────────────────────────────────────────────────────


def test_invalid_profile_rejected(good_frame):
    f = good_frame()
    f["profile"] = "bogus_v3"
    errs = validate_frame(f)
    assert any("profile" in e and "bogus_v3" in e for e in errs)


def test_embodiment_id_validates():
    f = {
        "index": 0, "episode_index": 0, "task_index": 0, "frame_index": 0,
        "t_ns": 1_000_000, "t_hw_ns": 1_000_000_000,
        "timestamp": "2026-07-21T00:00:00.000Z",
        "head_pose_SE3": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        "observation.state": [0.0] * 7,
        "observation.images.ego": "",
        "action": [0.0] * 6,
        "spatial_anchor_id": None,
        "source.device": "robot", "source.modality": "robot_replay",
        "tracking_state": "TRACKING",
        "embodiment_id": "some_robot_v1",
    }
    assert validate_frame(f) == []


def test_embodiment_id_empty_string_rejected():
    f = {
        "index": 0, "episode_index": 0, "task_index": 0, "frame_index": 0,
        "t_ns": 1_000_000, "t_hw_ns": 1_000_000_000,
        "timestamp": "2026-07-21T00:00:00.000Z",
        "head_pose_SE3": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        "observation.state": [0.0] * 7,
        "observation.images.ego": "",
        "action": [0.0] * 6,
        "spatial_anchor_id": None,
        "source.device": "robot", "source.modality": "robot_replay",
        "tracking_state": "TRACKING",
        "embodiment_id": "",
    }
    errs = validate_frame(f)
    assert any("embodiment_id" in e for e in errs)


def test_embodiment_id_none_accepted():
    """embodiment_id: null is OK (absent = no registry reference)."""
    f = {
        "index": 0, "episode_index": 0, "task_index": 0, "frame_index": 0,
        "t_ns": 1_000_000, "t_hw_ns": 1_000_000_000,
        "timestamp": "2026-07-21T00:00:00.000Z",
        "head_pose_SE3": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        "observation.state": [0.0] * 7,
        "observation.images.ego": "",
        "action": [0.0] * 6,
        "spatial_anchor_id": None,
        "source.device": "phone", "source.modality": "ego_human",
        "tracking_state": "TRACKING",
        "embodiment_id": None,
    }
    assert validate_frame(f) == []


# ── Dual-airbot example episode ─────────────────────────────────────────────────


def test_dual_airbot_example_exists():
    assert DUAL_AIRBOT.exists()


def test_dual_airbot_example_validates():
    frames = read_jsonl(DUAL_AIRBOT)
    report = validate_frames(frames)
    assert report.ok, report.errors
    assert report.total == 2 and report.valid == 2


def test_dual_airbot_frames_have_robot_v2_profile():
    frames = read_jsonl(DUAL_AIRBOT)
    for f in frames:
        assert f["profile"] == "robot_v2"
        assert "embodiment_id" in f
        assert f["embodiment_id"] == "dual_airbot_v1"
        # Should have multi-camera keys
        assert "observation.images.wrist_left" in f
        assert "observation.images.wrist_right" in f
        # Should have eef_pose
        assert "observation.eef_pose.left" in f
        assert "observation.eef_pose.right" in f
        # Variable-length vectors (14 DoF for dual arm)
        assert len(f["observation.state"]) == 14
        assert len(f["action"]) == 14


# ── required_keys_for_profile ───────────────────────────────────────────────────


def test_required_keys_ego_v1():
    keys = required_keys_for_profile("ego_v1")
    assert "observation.images.ego" in keys


def test_required_keys_robot_v2():
    keys = required_keys_for_profile("robot_v2")
    assert "observation.images.ego" not in keys
    assert "observation.state" in keys
    assert "action" in keys


def test_required_keys_default():
    assert required_keys_for_profile(None) == required_keys_for_profile("ego_v1")