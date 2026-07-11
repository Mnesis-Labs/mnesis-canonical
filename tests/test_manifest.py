"""Tests for the episode manifest writer (F1)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mnesis_canonical import (
    build_manifest,
    manifest_for_episode,
    read_jsonl,
    write_manifest,
)

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
EPISODES = sorted(EXAMPLES_DIR.glob("*/data.jsonl"))

_MANIFEST_KEYS = {
    "episodeIndex",
    "frameCount",
    "jsonlSizeBytes",
    "videoPath",
    "videoSizeBytes",
    "durationMs",
}


def test_build_manifest_rejects_empty():
    with pytest.raises(ValueError):
        build_manifest([], jsonl_size_bytes=0)


def test_build_manifest_duration_from_t_ns():
    frames = [
        {"episode_index": 7, "t_ns": 1_000_000},
        {"episode_index": 7, "t_ns": 5_000_000},
    ]
    m = build_manifest(frames, jsonl_size_bytes=123)
    assert m["episodeIndex"] == 7
    assert m["frameCount"] == 2
    assert m["durationMs"] == 4  # (5e6 - 1e6) ns = 4 ms
    assert m["videoPath"] is None and m["videoSizeBytes"] == 0


@pytest.mark.parametrize("jsonl", EPISODES, ids=lambda p: p.parent.name)
def test_manifest_for_each_example_is_consistent(jsonl):
    m = manifest_for_episode(jsonl.parent)
    assert set(m) == _MANIFEST_KEYS
    frames = read_jsonl(jsonl)
    assert m["frameCount"] == len(frames)
    assert m["episodeIndex"] == frames[0]["episode_index"]
    # Size must reflect the real on-disk sidecar (deterministic via .gitattributes LF).
    assert m["jsonlSizeBytes"] == jsonl.stat().st_size
    assert isinstance(m["durationMs"], int) and m["durationMs"] >= 0


def test_write_manifest_roundtrips(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "data.jsonl").write_text(
        '{"episode_index":3,"t_ns":1000000}\n{"episode_index":3,"t_ns":2000000}\n',
        encoding="utf-8",
    )
    out = write_manifest(ep)
    assert out == ep / "manifest.json"
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written == manifest_for_episode(ep)
    assert written["frameCount"] == 2 and written["episodeIndex"] == 3


# ── validate_manifest (S2-5) ──────────────────────────────────────────────────


from mnesis_canonical import validate_manifest  # noqa: E402


def test_validate_manifest_consistent(tmp_path):
    """Golden path: matching manifest passes."""
    ep = tmp_path / "ep"
    ep.mkdir()
    jsonl = ep / "data.jsonl"
    jsonl.write_text(
        '{"episode_index":1,"t_ns":1000000}\n{"episode_index":1,"t_ns":2000000}\n',
        encoding="utf-8",
    )
    jsonl_bytes = jsonl.stat().st_size
    manifest = ep / "manifest.json"
    manifest.write_text(
        json.dumps({
            "episodeIndex": 1,
            "frameCount": 2,
            "jsonlSizeBytes": jsonl_bytes,
            "videoPath": None,
            "videoSizeBytes": 0,
            "durationMs": 1,
        }),
        encoding="utf-8",
    )
    result = validate_manifest(ep)
    assert result["ok"] is True, result["errors"]


def test_validate_manifest_frame_count_mismatch(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    jsonl = ep / "data.jsonl"
    jsonl.write_text(
        '{"episode_index":0,"t_ns":1000000}\n{"episode_index":0,"t_ns":2000000}\n',
        encoding="utf-8",
    )
    jsonl_bytes = jsonl.stat().st_size
    manifest = ep / "manifest.json"
    manifest.write_text(
        json.dumps({
            "episodeIndex": 0,
            "frameCount": 999,  # wrong
            "jsonlSizeBytes": jsonl_bytes,
            "videoPath": None,
            "videoSizeBytes": 0,
            "durationMs": 1,
        }),
        encoding="utf-8",
    )
    result = validate_manifest(ep)
    assert result["ok"] is False
    assert any("frameCount" in e for e in result["errors"])


def test_validate_manifest_episode_index_mismatch(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    jsonl = ep / "data.jsonl"
    jsonl.write_text(
        '{"episode_index":0,"t_ns":1000000}\n',
        encoding="utf-8",
    )
    jsonl_bytes = jsonl.stat().st_size
    manifest = ep / "manifest.json"
    manifest.write_text(
        json.dumps({
            "episodeIndex": 99,  # wrong
            "frameCount": 1,
            "jsonlSizeBytes": jsonl_bytes,
            "videoPath": None,
            "videoSizeBytes": 0,
            "durationMs": 0,
        }),
        encoding="utf-8",
    )
    result = validate_manifest(ep)
    assert result["ok"] is False
    assert any("episodeIndex" in e for e in result["errors"])


def test_validate_manifest_jsonl_size_mismatch(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    jsonl = ep / "data.jsonl"
    jsonl.write_text(
        '{"episode_index":0,"t_ns":1000000}\n',
        encoding="utf-8",
    )
    manifest = ep / "manifest.json"
    manifest.write_text(
        json.dumps({
            "episodeIndex": 0,
            "frameCount": 1,
            "jsonlSizeBytes": 0,  # wrong
            "videoPath": None,
            "videoSizeBytes": 0,
            "durationMs": 0,
        }),
        encoding="utf-8",
    )
    result = validate_manifest(ep)
    assert result["ok"] is False
    assert any("jsonlSizeBytes" in e for e in result["errors"])


def test_validate_manifest_missing_manifest(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "data.jsonl").write_text("{}", encoding="utf-8")
    result = validate_manifest(ep)
    assert result["ok"] is False
    assert any("manifest not found" in e for e in result["errors"])


def test_validate_manifest_missing_jsonl(tmp_path):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "manifest.json").write_text("{}", encoding="utf-8")
    result = validate_manifest(ep)
    assert result["ok"] is False
    assert any("data.jsonl not found" in e for e in result["errors"])


# ── CLI tests for manifest --check ────────────────────────────────────────────


def test_cli_manifest_check_consistent(tmp_path, capsys):
    ep = tmp_path / "ep"
    ep.mkdir()
    jsonl = ep / "data.jsonl"
    jsonl.write_text(
        '{"episode_index":5,"t_ns":1000000}\n',
        encoding="utf-8",
    )
    from mnesis_canonical.__main__ import main as cli_main

    # write a correct manifest first
    cli_main(["manifest", str(ep)])
    capsys.readouterr()  # flush
    rc = cli_main(["manifest", str(ep), "--check"])
    assert rc == 0
    assert "consistent" in capsys.readouterr().out


def test_cli_manifest_check_inconsistent(tmp_path, capsys):
    ep = tmp_path / "ep"
    ep.mkdir()
    jsonl = ep / "data.jsonl"
    jsonl.write_text(
        '{"episode_index":5,"t_ns":1000000}\n',
        encoding="utf-8",
    )
    from mnesis_canonical.__main__ import main as cli_main
    from mnesis_canonical.manifest import manifest_for_episode

    manifest = manifest_for_episode(ep)
    manifest["frameCount"] = 999  # corrupt
    (ep / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    rc = cli_main(["manifest", str(ep), "--check"])
    assert rc == 1
    assert "frameCount" in capsys.readouterr().err
