"""Tests for CLI, LeRobot adapter, JSON Schema file, and multi-surface examples."""
from __future__ import annotations

import json
from pathlib import Path

from mnesis_canonical import (
    REQUIRED_KEYS,
    from_lerobot,
    read_jsonl,
    to_lerobot,
    validate_frames,
)
from mnesis_canonical.__main__ import main as cli_main

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


def test_cli_validate_ok():
    assert cli_main(["validate", str(EXAMPLES / "episode_0" / "data.jsonl")]) == 0


def test_cli_validate_bad(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"index":0,"frame_index":0}\n')  # missing required keys
    assert cli_main(["validate", str(bad)]) == 1


def test_multi_surface_examples_valid():
    for name in ("episode_0", "episode_quest", "episode_robot"):
        report = validate_frames(read_jsonl(EXAMPLES / name / "data.jsonl"))
        assert report.ok, (name, report.errors)


def test_lerobot_roundtrip():
    frames = read_jsonl(EXAMPLES / "episode_0" / "data.jsonl")
    cols = to_lerobot(frames)
    assert len(cols["index"]) == len(frames)
    back = from_lerobot(cols)
    # The LeRobot columns survive the round-trip.
    for a, b in zip(frames, back, strict=True):
        for col in cols:
            assert a[col] == b[col]


def test_json_schema_file_matches_required_keys():
    schema = json.loads((ROOT / "mnesis_canonical" / "canonical_frame.schema.json").read_text())
    assert set(schema["required"]) == set(REQUIRED_KEYS)
    for key in REQUIRED_KEYS:
        assert key in schema["properties"], f"{key} missing from JSON Schema properties"
