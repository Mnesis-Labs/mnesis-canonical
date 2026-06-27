"""Tests for the Canonical Schema reference validator + the example episode."""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mnesis_canonical import (
    CanonicalFrame,
    load_json_schema,
    read_jsonl,
    validate_frame,
    validate_frame_jsonschema,
    validate_frames,
)

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


def test_good_frame_validates():
    assert validate_frame(_good_frame()) == []


def test_missing_key_fails():
    f = _good_frame()
    del f["t_hw_ns"]
    errs = validate_frame(f)
    assert any("t_hw_ns" in e for e in errs)


def test_wrong_vector_length_fails():
    f = _good_frame()
    f["action"] = [1.0, 2.0, 3.0]  # should be length 6
    errs = validate_frame(f)
    assert any("action" in e and "length 6" in e for e in errs)


def test_head_pose_must_be_7():
    f = _good_frame()
    f["head_pose_SE3"] = [0.0] * 6
    assert any("head_pose_SE3" in e for e in validate_frame(f))


def test_strict_vocab_rejects_unknown_device():
    f = _good_frame()
    f["source.device"] = "hololens"
    assert validate_frame(f) == []  # lenient by default
    assert any("source.device" in e for e in validate_frame(f, strict_vocab=True))


def test_example_episode_is_valid():
    frames = read_jsonl(EXAMPLE)
    report = validate_frames(frames)
    assert report.ok, report.errors
    assert report.total == 2 and report.valid == 2


def test_frame_index_must_increase():
    frames = [_good_frame(), copy.deepcopy(_good_frame())]  # both frame_index=0
    report = validate_frames(frames)
    assert not report.ok
    assert any("frame_index not increasing" in m for _, m in report.errors)


def test_dataclass_roundtrip():
    d = _good_frame()
    assert CanonicalFrame.from_dict(d).to_dict() == d


# --- JSON Schema backend (C1) -------------------------------------------------

def test_json_schema_loads_and_matches_required_keys():
    schema = load_json_schema()
    assert schema["$schema"].endswith("2020-12/schema")
    # The bundled JSON Schema and the Python REQUIRED_KEYS must not drift.
    from mnesis_canonical import REQUIRED_KEYS

    assert set(schema["required"]) == set(REQUIRED_KEYS)


def test_example_passes_both_validators():
    pytest.importorskip("jsonschema")
    for frame in read_jsonl(EXAMPLE):
        assert validate_frame(frame) == []
        assert validate_frame_jsonschema(frame) == []


def test_jsonschema_backend_rejects_bad_frame():
    pytest.importorskip("jsonschema")
    f = _good_frame()
    f["action"] = [1.0, 2.0, 3.0]  # wrong length (should be 6)
    assert validate_frame_jsonschema(f)  # non-empty error list
