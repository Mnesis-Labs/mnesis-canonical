"""Tests for the `python -m mnesis_canonical` CLI (validate / manifest)."""
from __future__ import annotations

import json
from pathlib import Path

from mnesis_canonical.__main__ import main

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "episode_0" / "data.jsonl"


def test_cli_valid_example_returns_zero(capsys):
    assert main(["validate", str(EXAMPLE)]) == 0
    out = capsys.readouterr().out
    assert "total=2" in out and "valid=2" in out and "errors=0" in out


def test_cli_bad_episode_returns_one(tmp_path, capsys, good_frame):
    bad = tmp_path / "data.jsonl"
    f = good_frame()
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
