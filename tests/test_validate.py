"""Tests for the Canonical Schema reference validator + the example episode."""
from __future__ import annotations

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


def test_good_frame_validates(good_frame):
    assert validate_frame(good_frame()) == []


def test_missing_key_fails(good_frame):
    f = good_frame()
    del f["t_hw_ns"]
    errs = validate_frame(f)
    assert any("t_hw_ns" in e for e in errs)


def test_wrong_vector_length_fails(good_frame):
    f = good_frame()
    f["action"] = [1.0, 2.0, 3.0]  # should be length 6
    errs = validate_frame(f)
    assert any("action" in e and "length 6" in e for e in errs)


def test_head_pose_must_be_7(good_frame):
    f = good_frame()
    f["head_pose_SE3"] = [0.0] * 6
    assert any("head_pose_SE3" in e for e in validate_frame(f))


def test_strict_vocab_rejects_unknown_device(good_frame):
    f = good_frame()
    f["source.device"] = "hololens"
    assert validate_frame(f) == []  # lenient by default
    assert any("source.device" in e for e in validate_frame(f, strict_vocab=True))


def test_example_episode_is_valid():
    frames = read_jsonl(EXAMPLE)
    report = validate_frames(frames)
    assert report.ok, report.errors
    assert report.total == 2 and report.valid == 2


def test_frame_index_must_increase(good_frame):
    frames = [good_frame(), good_frame()]  # both frame_index=0
    report = validate_frames(frames)
    assert not report.ok
    assert any("duplicate frame_index" in m for _, m in report.errors)


def test_dataclass_roundtrip(good_frame):
    d = good_frame()
    assert CanonicalFrame.from_dict(d).to_dict() == d


# --- JSON Schema backend ------------------------------------------------------

def test_json_schema_loads_and_matches_required_keys():
    schema = load_json_schema()
    assert schema["$schema"].endswith("2020-12/schema")
    # The bundled JSON Schema top-level required is the intersection of all
    # profile required sets (without observation.images.ego, which is conditional).
    # The Python REQUIRED_KEYS is the ego_v1 set (backward compat superset).
    from mnesis_canonical import REQUIRED_KEYS, required_keys_for_profile

    schema_top_required = set(schema["required"])
    robot_v2_required = set(required_keys_for_profile("robot_v2"))
    # Schema top-level must be exactly the robot_v2 required set
    assert schema_top_required == robot_v2_required
    # Python REQUIRED_KEYS (ego_v1) is a superset
    assert set(REQUIRED_KEYS) >= robot_v2_required


def test_example_passes_both_validators():
    pytest.importorskip("jsonschema")
    for frame in read_jsonl(EXAMPLE):
        assert validate_frame(frame) == []
        assert validate_frame_jsonschema(frame) == []


def test_jsonschema_backend_rejects_bad_frame(good_frame):
    pytest.importorskip("jsonschema")
    f = good_frame()
    f["action"] = [1.0, 2.0, 3.0]  # wrong length (should be 6)
    assert validate_frame_jsonschema(f)  # non-empty error list


# --- S2-3: Boundary hardening -------------------------------------------------

def test_nan_in_vector_rejected(good_frame):
    f = good_frame()
    f["action"] = [1.0, float("nan"), 3.0, 4.0, 5.0, 6.0]
    errs = validate_frame(f)
    assert any("action" in e and "finite" in e for e in errs)


def test_inf_in_vector_rejected(good_frame):
    f = good_frame()
    f["head_pose_SE3"] = [0.0, 0.0, 0.0, 0.0, 0.0, float("inf"), 1.0]
    errs = validate_frame(f)
    assert any("head_pose_SE3" in e and "finite" in e for e in errs)


def test_finite_vector_accepted(good_frame):
    f = good_frame()
    f["action"] = [1.0, -2.5, 3.0, 0.0, 0.5, -1.0]
    assert validate_frame(f) == []


def test_duplicate_frame_index_rejected(good_frame):
    f0 = good_frame()
    f1 = good_frame()  # both frame_index=0
    f1["t_ns"] = 2_000_000
    f1["t_hw_ns"] = 2_000_000_000
    report = validate_frames([f0, f1])
    assert not report.ok
    assert any("duplicate frame_index" in m for _, m in report.errors)


def test_negative_frame_index_rejected(good_frame):
    f = good_frame()
    f["frame_index"] = -1
    report = validate_frames([f])
    assert not report.ok
    assert any("non-negative" in m for _, m in report.errors)


def test_positive_frame_index_increasing_accepted(good_frame):
    f0 = good_frame()
    f1 = good_frame()
    f1["frame_index"] = 1
    f1["t_ns"] = 2_000_000
    f1["t_hw_ns"] = 2_000_000_000
    report = validate_frames([f0, f1])
    assert report.ok


# --- S2-10: spatial_anchor_id episode-level validation ------------------------


def test_duplicate_spatial_anchor_rejected(good_frame):
    """Same anchor_id in two frames → duplicate definition error."""
    f0 = good_frame()
    f0["spatial_anchor_id"] = "anchor-A"
    f1 = good_frame()
    f1["frame_index"] = 1
    f1["t_ns"] = 2_000_000
    f1["t_hw_ns"] = 2_000_000_000
    f1["spatial_anchor_id"] = "anchor-A"
    report = validate_frames([f0, f1])
    assert not report.ok
    assert any("duplicate" in m and "anchor-A" in m for _, m in report.errors)


def test_undefined_spatial_anchor_rejected(good_frame):
    """Empty string spatial_anchor_id → undefined/reference error."""
    f = good_frame()
    f["spatial_anchor_id"] = ""
    errs = validate_frame(f)
    assert any("spatial_anchor_id" in e and "empty" in e for e in errs)


def test_unique_spatial_anchors_accepted(good_frame):
    """Different anchor_ids across frames → valid."""
    f0 = good_frame()
    f0["spatial_anchor_id"] = "anchor-A"
    f1 = good_frame()
    f1["frame_index"] = 1
    f1["t_ns"] = 2_000_000
    f1["t_hw_ns"] = 2_000_000_000
    f1["spatial_anchor_id"] = "anchor-B"
    report = validate_frames([f0, f1])
    assert report.ok


def test_null_spatial_anchor_accepted(good_frame):
    """None spatial_anchor_id → skip (no anchor)."""
    f = good_frame()
    assert f["spatial_anchor_id"] is None
    assert validate_frame(f) == []


def test_multiple_duplicate_anchor_errors(good_frame):
    """Three frames with the same anchor_id → error on each duplicate."""
    f0 = good_frame()
    f0["spatial_anchor_id"] = "anchor-X"
    f1 = good_frame()
    f1["frame_index"] = 1
    f1["t_ns"] = 2_000_000
    f1["t_hw_ns"] = 2_000_000_000
    f1["spatial_anchor_id"] = "anchor-X"
    f2 = good_frame()
    f2["frame_index"] = 2
    f2["t_ns"] = 3_000_000
    f2["t_hw_ns"] = 3_000_000_000
    f2["spatial_anchor_id"] = "anchor-X"
    report = validate_frames([f0, f1, f2])
    assert not report.ok
    assert len(report.errors) == 2  # two duplicates of anchor-X
    assert all("duplicate" in m and "anchor-X" in m for _, m in report.errors)


def test_anchor_errors_include_cli_in_output(capsys, tmp_path, good_frame):
    """CLI validate exits 1 and prints anchor errors to stderr."""
    from mnesis_canonical.__main__ import main

    bad = tmp_path / "data.jsonl"
    f0 = good_frame()
    f0["spatial_anchor_id"] = "anchor-A"
    f1 = good_frame()
    f1["frame_index"] = 1
    f1["t_ns"] = 2_000_000
    f1["t_hw_ns"] = 2_000_000_000
    f1["spatial_anchor_id"] = "anchor-A"
    import json
    bad.write_text(
        json.dumps(f0) + "\n" + json.dumps(f1) + "\n", encoding="utf-8"
    )
    rc = main(["validate", str(bad)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "duplicate" in err and "anchor-A" in err
