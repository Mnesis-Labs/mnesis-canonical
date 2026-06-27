"""Tests for the LeRobot columnar adapter (C3)."""
from __future__ import annotations

from pathlib import Path

from mnesis_canonical import (
    LEROBOT_FEATURES,
    from_lerobot,
    read_jsonl,
    to_lerobot,
)

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "episode_0" / "data.jsonl"


def test_to_lerobot_exposes_native_features():
    frames = read_jsonl(EXAMPLE)
    columns = to_lerobot(frames)
    # Every LeRobot-native feature must be present as a column, 1:1, no renaming.
    for feature in LEROBOT_FEATURES:
        assert feature in columns
        assert len(columns[feature]) == len(frames)
    # Column values match the source rows.
    assert columns["frame_index"] == [f["frame_index"] for f in frames]


def test_round_trip_is_exact():
    frames = read_jsonl(EXAMPLE)
    assert from_lerobot(to_lerobot(frames)) == frames


def test_round_trip_without_optional_key():
    frames = read_jsonl(EXAMPLE)
    for f in frames:
        f.pop("spatial_anchor_id", None)  # frames lacking the optional key
    columns = to_lerobot(frames)
    assert "spatial_anchor_id" not in columns  # not invented
    assert from_lerobot(columns) == frames


def test_from_lerobot_ignores_extra_columns():
    frames = read_jsonl(EXAMPLE)
    columns = to_lerobot(frames)
    columns["some_extra_feature"] = [None] * len(frames)  # non-canonical
    assert from_lerobot(columns) == frames
