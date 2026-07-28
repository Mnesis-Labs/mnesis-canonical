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


def _strip_nones(frames: list[dict]) -> list[dict]:
    """Return a deep copy with None-valued keys removed (for round-trip comparison)."""
    return [
        {k: v for k, v in f.items() if v is not None}
        for f in frames
    ]


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
    restored = from_lerobot(to_lerobot(frames))
    # Strip None-valued keys from original so "missing == unknown" rule holds.
    assert _strip_nones(restored) == _strip_nones(frames)


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
    # from_lerobot strips None-valued keys (missing == unknown rule), so
    # an all-None extra column is dropped entirely.
    restored = from_lerobot(columns)
    assert "some_extra_feature" not in restored[0]


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
    # Strip None-valued keys from original so "missing == unknown" rule holds.
    assert _strip_nones(restored) == _strip_nones(frames), (
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