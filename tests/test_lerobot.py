"""Tests for the LeRobot columnar adapter (C3)."""
from __future__ import annotations

from pathlib import Path

import pytest

from mnesis_canonical import (
    LEROBOT_FEATURES,
    from_lerobot,
    read_jsonl,
    to_lerobot,
)

EXAMPLE = Path(__file__).resolve().parent.parent / "examples"


def _episodes():
    """Return paths to all example episode data.jsonl files."""
    return sorted(EXAMPLE.glob("episode_*/data.jsonl"))


def test_to_lerobot_exposes_native_features():
    frames = read_jsonl(EXAMPLE / "episode_0" / "data.jsonl")
    columns = to_lerobot(frames)
    # Every LeRobot-native feature must be present as a column, 1:1, no renaming.
    for feature in LEROBOT_FEATURES:
        assert feature in columns
        assert len(columns[feature]) == len(frames)
    # Column values match the source rows.
    assert columns["frame_index"] == [f["frame_index"] for f in frames]


def test_round_trip_is_exact():
    frames = read_jsonl(EXAMPLE / "episode_0" / "data.jsonl")
    assert from_lerobot(to_lerobot(frames)) == frames


def test_round_trip_without_optional_key():
    frames = read_jsonl(EXAMPLE / "episode_0" / "data.jsonl")
    for f in frames:
        f.pop("spatial_anchor_id", None)  # frames lacking the optional key
    columns = to_lerobot(frames)
    assert "spatial_anchor_id" not in columns  # not invented
    assert from_lerobot(columns) == frames


def test_from_lerobot_ignores_extra_columns():
    """Non-canonical columns are still carried through (round-trip fidelity)."""
    frames = read_jsonl(EXAMPLE / "episode_0" / "data.jsonl")
    columns = to_lerobot(frames)
    columns["some_extra_feature"] = [None] * len(frames)  # non-canonical, all None
    # schema 不认识这一列，就没有立场判定它的 null 非法 —— 原样带过。
    # （#89 曾把本断言反转成 `not in` 以迁就 blanket 丢弃；schema 驱动后不需要了。）
    restored = from_lerobot(columns)
    assert "some_extra_feature" in restored[0]


# ── All example episodes ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [p.relative_to(EXAMPLE) for p in _episodes()],
    ids=[p.stem for p in _episodes()],
)
def test_round_trip_all_episodes(path):
    """to_lerobot → from_lerobot is exact for every example episode."""
    frames = read_jsonl(EXAMPLE / path)
    columns = to_lerobot(frames)
    restored = from_lerobot(columns)
    assert restored == frames, (
        f"Mismatch for {path}:\n"
        f"  frame keys:     {sorted(frames[0])}\n"
        f"  lerobot cols:   {sorted(columns)}\n"
        f"  restored keys:  {sorted(restored[0])}\n"
    )


@pytest.mark.parametrize(
    "path",
    [p.relative_to(EXAMPLE) for p in _episodes()],
    ids=[p.stem for p in _episodes()],
)
def test_no_dropped_or_invented_columns(path):
    """to_lerobot emits exactly the union of keys present across frames."""
    frames = read_jsonl(EXAMPLE / path)
    columns = to_lerobot(frames)
    frame_keys = set()
    for f in frames:
        frame_keys.update(f)
    lerobot_keys = set(columns)
    dropped = frame_keys - lerobot_keys
    invented = lerobot_keys - frame_keys
    assert not dropped, f"to_lerobot dropped keys from {path}: {sorted(dropped)}"
    assert not invented, f"to_lerobot invented keys for {path}: {sorted(invented)}"

# ── 稀疏可选键的往返（canonical#87 回归）────────────────────────────────────────
# 这里刻意**不针对 observation.hand.right 写死**。#67 那次只治了当时出问题的那一个
# 字段（observation.images.ego），机制原样留着，于是 #72 加进 observation.hand.* 之后
# 同一个 bug 立刻复发、把 main 红了 18 小时。所以这组用例测的是机制：
# 「schema 声明为非 null 的键，在某些帧缺失时，往返后不得凭空出现」。

def test_sparse_optional_key_is_not_fabricated():
    """frame1 没有的可选键，往返后不许冒出来（值为 None 也不行）。"""
    frames = [
        {"index": 0, "observation.hand.left": [0.0] * 63, "observation.hand.right": [0.1] * 63},
        {"index": 1, "observation.hand.left": [0.0] * 63},
    ]
    restored = from_lerobot(to_lerobot(frames))
    assert "observation.hand.right" not in restored[1]
    assert restored == frames


def test_schema_nullable_key_keeps_its_explicit_null():
    """schema 明确允许 null 的键（spatial_anchor_id），显式 null 必须原样保留。"""
    frames = [
        {"index": 0, "spatial_anchor_id": None},
        {"index": 1, "spatial_anchor_id": "anchor-a"},
    ]
    restored = from_lerobot(to_lerobot(frames))
    assert "spatial_anchor_id" in restored[0]
    assert restored[0]["spatial_anchor_id"] is None
    assert restored == frames


def test_unknown_extension_column_is_carried_through():
    """schema 不认识的键（厂商扩展）没有判定依据，一律原样带过，不擅自丢弃。"""
    frames = [{"index": 0, "x-vendor.thing": None}, {"index": 1, "x-vendor.thing": None}]
    restored = from_lerobot(to_lerobot(frames))
    assert all("x-vendor.thing" in f for f in restored)
    assert restored == frames
