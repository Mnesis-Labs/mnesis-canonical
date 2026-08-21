"""Conformance for the objects.jsonl side channel (C13).

The point of C13 is the ``pose_dof`` honesty rule: a single-view 2-D box +
depth back-projection cannot observe orientation, so a record MUST say
``pose_dof: 3`` with ``quat_wxyz: null`` unless a real orientation estimator
produced it. These tests pin that coupling (both directions), the stream-level
bookkeeping (frame monotonicity, track-count agreement, header/record
pose_dof agreement), and the schema/module lock-step.
"""

from __future__ import annotations

import pytest

from mnesis_canonical.objects_jsonl import (
    FRAME_DIALECTS,
    POSE_DOFS,
    POSE_FRAME,
    SCHEMA_VERSION,
    load_objects_jsonl_schema,
    validate_header,
    validate_line_jsonschema,
    validate_object_record,
    validate_objects_jsonl_stream,
)


def _header(**overrides) -> dict:
    base = {
        "type": "header",
        "version": SCHEMA_VERSION,
        "source": "lerobot.scene.object_track",
        "frame_dialect": "mono",
        "detector_backend": "onnx_cpu",
        "pose_frame": POSE_FRAME,
        "pose_dof": 3,
        "num_frames": 20,
        "num_tracks": 1,
    }
    base.update(overrides)
    return base


def _record(**overrides) -> dict:
    base = {
        "type": "object",
        "frame": 0,
        "track_id": "obj-0001",
        "class_id": "cup",
        "confidence": 0.9,
        "pose_dof": 3,
        "position_m": [1.8, 0.0, 1.09],
        "quat_wxyz": None,
        "depth_m": 1.8,
        "box_xyxy": [155.0, 115.0, 165.0, 125.0],
        "width_m": 0.1125,
        "height_m": 0.1125,
    }
    base.update(overrides)
    return base


# --- header -----------------------------------------------------------------


def test_valid_header_has_no_errors():
    assert validate_header(_header()) == []


def test_header_wrong_version_rejected():
    errors = validate_header(_header(version=2))
    assert any("version" in e for e in errors)


def test_header_unknown_dialect_rejected():
    errors = validate_header(_header(frame_dialect="fisheye"))
    assert any("frame_dialect" in e for e in errors)
    assert set(FRAME_DIALECTS) == {"mono", "iris"}


def test_header_wrong_pose_frame_rejected():
    errors = validate_header(_header(pose_frame="camera_local"))
    assert any("pose_frame" in e for e in errors)


def test_header_bad_pose_dof_rejected():
    errors = validate_header(_header(pose_dof=4))
    assert any("pose_dof" in e for e in errors)
    assert POSE_DOFS == (3, 6)


def test_header_negative_counts_rejected():
    errors = validate_header(_header(num_frames=-1, num_tracks=-1))
    assert any("num_frames" in e for e in errors)
    assert any("num_tracks" in e for e in errors)


def test_header_not_an_object_rejected():
    errors = validate_header("not-a-dict")
    assert errors and "JSON object" in errors[0]


# --- the pose_dof <-> quat_wxyz honesty rule (the point of this contract) ---


def test_pose_dof_3_with_null_quat_is_valid():
    assert validate_object_record(_record(pose_dof=3, quat_wxyz=None)) == []


def test_pose_dof_3_with_populated_quat_is_rejected():
    """The failure mode this whole contract exists to make impossible: faking
    6-DoF out of a position-only observation."""
    errors = validate_object_record(_record(pose_dof=3, quat_wxyz=[1.0, 0.0, 0.0, 0.0]))
    assert any("quat_wxyz must be null" in e for e in errors)


def test_pose_dof_6_requires_populated_unit_quat():
    errors = validate_object_record(_record(pose_dof=6, quat_wxyz=None))
    assert any("quat_wxyz" in e for e in errors)


def test_pose_dof_6_with_valid_unit_quat_is_valid():
    assert validate_object_record(_record(pose_dof=6, quat_wxyz=[1.0, 0.0, 0.0, 0.0])) == []


def test_pose_dof_6_with_non_unit_quat_is_rejected():
    errors = validate_object_record(_record(pose_dof=6, quat_wxyz=[2.0, 0.0, 0.0, 0.0]))
    assert any("unit quaternion" in e for e in errors)


def test_pose_dof_out_of_range_rejected():
    errors = validate_object_record(_record(pose_dof=0, quat_wxyz=None))
    assert any("pose_dof" in e for e in errors)


# --- other per-record fields --------------------------------------------


def test_valid_record_has_no_errors():
    assert validate_object_record(_record()) == []


@pytest.mark.parametrize("confidence", [-0.1, 1.1, float("nan"), None])
def test_confidence_out_of_range_rejected(confidence):
    errors = validate_object_record(_record(confidence=confidence))
    assert any("confidence" in e for e in errors)


def test_box_xyxy_must_be_ordered():
    errors = validate_object_record(_record(box_xyxy=[165.0, 115.0, 155.0, 125.0]))
    assert any("x1 < x2" in e for e in errors)


@pytest.mark.parametrize("key", ["depth_m", "width_m", "height_m"])
def test_non_positive_metric_fields_rejected(key):
    errors = validate_object_record(_record(**{key: 0.0}))
    assert any(key in e for e in errors)
    errors_neg = validate_object_record(_record(**{key: -1.0}))
    assert any(key in e for e in errors_neg)


def test_empty_track_id_or_class_id_rejected():
    errors = validate_object_record(_record(track_id=""))
    assert any("track_id" in e for e in errors)
    errors2 = validate_object_record(_record(class_id=""))
    assert any("class_id" in e for e in errors2)


def test_record_not_an_object_rejected():
    errors = validate_object_record(None)
    assert errors and "JSON object" in errors[0]


# --- stream-level cross-line invariants -------------------------------------


def test_valid_stream_has_no_errors():
    lines = [_header(num_frames=3, num_tracks=1)] + [_record(frame=i) for i in range(3)]
    assert validate_objects_jsonl_stream(lines) == []


def test_empty_stream_rejected():
    errors = validate_objects_jsonl_stream([])
    assert errors and "empty file" in errors[0]


def test_extra_header_line_rejected():
    lines = [_header(), _header(), _record()]
    errors = validate_objects_jsonl_stream(lines)
    assert any("additional 'header' lines" in e for e in errors)


def test_record_pose_dof_mismatching_header_rejected():
    lines = [_header(pose_dof=3), _record(pose_dof=6, quat_wxyz=[1.0, 0.0, 0.0, 0.0])]
    errors = validate_objects_jsonl_stream(lines)
    assert any("does not match header.pose_dof" in e for e in errors)


def test_decreasing_frame_rejected():
    lines = [_header(num_frames=2, num_tracks=1), _record(frame=1), _record(frame=0)]
    errors = validate_objects_jsonl_stream(lines)
    assert any("non-decreasing" in e for e in errors)


def test_num_tracks_mismatch_rejected():
    lines = [
        _header(num_tracks=2),
        _record(track_id="obj-0001"),
        _record(track_id="obj-0001"),  # only ONE distinct track_id, header says 2
    ]
    errors = validate_objects_jsonl_stream(lines)
    assert any("num_tracks" in e and "does not match" in e for e in errors)


def test_num_tracks_counts_distinct_track_ids_correctly():
    lines = [
        _header(num_tracks=2),
        _record(track_id="obj-0001"),
        _record(track_id="obj-0002"),
    ]
    assert validate_objects_jsonl_stream(lines) == []


def test_stream_propagates_header_and_record_errors():
    lines = [_header(version=99), _record(confidence=-1)]
    errors = validate_objects_jsonl_stream(lines)
    assert any("version" in e for e in errors)
    assert any("confidence" in e for e in errors)


# --- schema / module lock-step -----------------------------------------------


def test_schema_loads_and_is_draft_2020_12():
    schema = load_objects_jsonl_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert "header" in schema["$defs"]
    assert "object_record" in schema["$defs"]


def test_jsonschema_accepts_valid_header_and_record():
    pytest.importorskip("jsonschema")
    assert validate_line_jsonschema(_header()) == []
    assert validate_line_jsonschema(_record()) == []


def test_jsonschema_rejects_pose_dof_3_with_populated_quat():
    pytest.importorskip("jsonschema")
    errors = validate_line_jsonschema(_record(pose_dof=3, quat_wxyz=[1.0, 0.0, 0.0, 0.0]))
    assert errors, "JSON Schema should also catch the pose_dof/quat_wxyz coupling"


def test_jsonschema_without_dependency_raises_runtime_error(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def _blocked(name, *a, **kw):
        if name == "jsonschema":
            raise ImportError("blocked for test")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", _blocked)
    with pytest.raises(RuntimeError, match="jsonschema"):
        validate_line_jsonschema(_header())
