"""Tests for the Isaac/GR00T export adapter (F2) — adapter-only, wire unchanged."""
from __future__ import annotations

from pathlib import Path

from mnesis_canonical import (
    from_isaac,
    quat_wxyz_to_xyzw,
    quat_xyzw_to_wxyz,
    read_jsonl,
    to_isaac,
)

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "episode_0" / "data.jsonl"


def test_quat_reorder_and_inverse():
    assert quat_xyzw_to_wxyz([1.0, 2.0, 3.0, 4.0]) == [4.0, 1.0, 2.0, 3.0]
    assert quat_wxyz_to_xyzw([4.0, 1.0, 2.0, 3.0]) == [1.0, 2.0, 3.0, 4.0]


def test_to_isaac_makes_quaternion_scalar_first():
    frames = read_jsonl(EXAMPLE)
    isaac = to_isaac(frames)
    # canonical head_pose_SE3[0] = [0,0,0, 0,0,0,1] (qw last) -> [0,0,0, 1,0,0,0] (qw first)
    assert isaac[0]["head_pose_SE3"] == [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
    assert isaac[0]["observation.state"] == [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
    # translation untouched; action left verbatim (待对齐).
    assert isaac[0]["action"] == frames[0]["action"]


def test_to_isaac_does_not_mutate_input():
    frames = read_jsonl(EXAMPLE)
    before = [list(f["head_pose_SE3"]) for f in frames]
    to_isaac(frames)
    assert [f["head_pose_SE3"] for f in frames] == before


def test_round_trip_is_exact():
    frames = read_jsonl(EXAMPLE)
    assert from_isaac(to_isaac(frames)) == frames


def test_world_transform_hook_round_trips():
    frames = read_jsonl(EXAMPLE)

    def shift(p):  # +1 on tx, identity on rotation
        return [p[0] + 1.0, *p[1:]]

    def unshift(p):
        return [p[0] - 1.0, *p[1:]]

    isaac = to_isaac(frames, world_transform=shift)
    assert isaac[0]["head_pose_SE3"][0] == frames[0]["head_pose_SE3"][0] + 1.0
    # still scalar-first quaternion
    assert isaac[0]["head_pose_SE3"][3:] == [1.0, 0.0, 0.0, 0.0]
    assert from_isaac(isaac, world_transform=unshift) == frames


def test_reorder_quat_false_leaves_quaternion_order():
    frames = read_jsonl(EXAMPLE)
    isaac = to_isaac(frames, reorder_quat=False)
    assert isaac[0]["head_pose_SE3"] == frames[0]["head_pose_SE3"]
