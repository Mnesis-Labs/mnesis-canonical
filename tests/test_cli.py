"""Tests for the `python -m mnesis_canonical validate` CLI (C2)."""
from __future__ import annotations

import json
from pathlib import Path

from mnesis_canonical.__main__ import main

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "episode_0" / "data.jsonl"


def _good_frame() -> dict:
    return {
        "index": 0, "episode_index": 0, "task_index": 0, "frame_index": 0,
        "t_ns": 1_000_000, "t_hw_ns": 1_000_000_000,
        "timestamp": "2026-06-26T00:00:00.000Z",
        "head_pose_SE3": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        "observation.state": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        "observation.images.ego": "",
        "action": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "spatial_anchor_id": None,
        "source.device": "phone", "source.modality": "ego_human",
        "tracking_state": "TRACKING",
    }


def test_cli_valid_example_returns_zero(capsys):
    assert main(["validate", str(EXAMPLE)]) == 0
    out = capsys.readouterr().out
    assert "total=2" in out and "valid=2" in out and "errors=0" in out


def test_cli_bad_episode_returns_one(tmp_path, capsys):
    bad = tmp_path / "data.jsonl"
    f = _good_frame()
    del f["t_hw_ns"]  # missing required key
    bad.write_text(json.dumps(f) + "\n", encoding="utf-8")
    assert main(["validate", str(bad)]) == 1
    err = capsys.readouterr().err
    assert "t_hw_ns" in err


def test_cli_missing_file_returns_two(capsys):
    assert main(["validate", "does/not/exist.jsonl"]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_empty_episode_returns_one(tmp_path):
    empty = tmp_path / "data.jsonl"
    empty.write_text("", encoding="utf-8")
    assert main(["validate", str(empty)]) == 1


def test_cli_manifest_no_write(capsys):
    rc = main(["manifest", str(EXAMPLE.parent), "--no-write"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["frameCount"] == 2 and out["episodeIndex"] == 0


def test_cli_manifest_missing_dir_returns_two(capsys):
    assert main(["manifest", "does/not/exist"]) == 2
    assert "no data.jsonl" in capsys.readouterr().err


def test_cli_demo_generates_artifacts(tmp_path):
    out = tmp_path / "demo_out"
    assert main(["demo", "--out", str(out)]) == 0
    for name in ("episode_phone", "episode_quest", "episode_robot"):
        assert (out / "episodes" / name / "data.jsonl").exists()
        assert (out / "episodes" / name / "manifest.json").exists()
        assert (out / "lerobot" / f"{name}.columns.json").exists()
        assert (out / "isaac" / f"{name}.jsonl").exists()
