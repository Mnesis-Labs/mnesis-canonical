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
