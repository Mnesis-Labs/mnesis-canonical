"""Tests for the `python -m mnesis_canonical` CLI (validate / manifest / convert)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from mnesis_canonical.__main__ import main

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "episode_0" / "data.jsonl"


def test_cli_schema_version_exists(capsys):
    """--schema-version prints a non-empty version string and exits 0."""
    rc = main(["--schema-version"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out, "schema-version output must not be empty"
    assert re.match(r"^v?\d+\.\d+", out), f"schema-version '{out}' does not look like a version"


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


# --- S2-4: convert CLI --------------------------------------------------------


def test_cli_convert_lerobot_outputs_columnar_json(tmp_path):
    out = tmp_path / "lerobot.json"
    rc = main(["convert", str(EXAMPLE), "--to", "lerobot", "--out", str(out)])
    assert rc == 0
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "action" in data
    assert "observation.state" in data
    assert isinstance(data["action"], list)
    assert len(data["action"]) == 2


def test_cli_convert_isaac_outputs_jsonl(tmp_path):
    out = tmp_path / "isaac.jsonl"
    rc = main(["convert", str(EXAMPLE), "--to", "isaac", "--out", str(out)])
    assert rc == 0
    assert out.exists()
    lines = [json.loads(line) for line in out.read_text(encoding="utf-8").strip().splitlines()]
    assert len(lines) == 2
    # Isaac-flavoured frames still contain the same keys
    assert "action" in lines[0]


def test_cli_convert_unknown_format_returns_one(tmp_path, capsys):
    out = tmp_path / "out.json"
    rc = main(["convert", str(EXAMPLE), "--to", "nonexistent", "--out", str(out)])
    assert rc == 1
    assert "unknown format" in capsys.readouterr().err


def test_cli_convert_missing_source_returns_two(tmp_path, capsys):
    out = tmp_path / "out.json"
    rc = main(["convert", "does/not/exist.jsonl", "--to", "lerobot", "--out", str(out)])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


def test_cli_convert_lerobot_output_is_lf(tmp_path):
    """Verify lerobot output uses LF line ending (not CRLF)."""
    out = tmp_path / "lerobot.json"
    main(["convert", str(EXAMPLE), "--to", "lerobot", "--out", str(out)])
    raw = out.read_bytes()
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n")
