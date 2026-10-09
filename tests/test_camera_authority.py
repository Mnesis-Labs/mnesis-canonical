"""C9 CPU-only golden/negative cases; synthetic receipts are never hardware proof."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from enum import Enum
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from mnesis_canonical.camera_authority import (
    compose_sensor_pose,
    load_camera_authority_schema,
    validate_camera_authority,
    validate_camera_authority_binding,
)


def golden():
    # Fixed synthetic receipt bytes: actual test evidence, not invented device hashes.
    def evidence(name):
        return {"ref": name + ".json", "sha256": hashlib.sha256(name.encode()).hexdigest(),
                "fixture": True}

    q = math.sqrt(0.5)
    return {
        "schema_version": "camera-authority/1.0", "episode_id": "fixture-episode",
        "frame_index": 7, "image_key": "observation.images.ego",
        "image_ref": "frames/000007.jpg", "image_sha256": "a" * 64,
        "sensor_id": "left_rgb", "world_frame_id": "local-world-1",
        "provider": {"id": "synthetic-provider", "version": "fixture-v1",
                     "evidence": evidence("provider")},
        "intrinsics": {"model": "undistorted_pinhole", "width": 640, "height": 480,
                       "K": [400, 0, 320, 0, 400, 240, 0, 0, 1], "calibration_id": "cal-1",
                       "calibration_revision": "fixture-r1"},
        "calibration": {"calibration_id": "cal-1", "revision": "fixture-r1",
                        "sensor_id": "left_rgb",
                        "head_frame_id": "head", "T_head_sensor": [0.1, 0, 0, 0, q, 0, q],
                        "evidence": evidence("calibration")},
        "clock_mapping": {"source_clock_id": "camera_hw", "target_clock_id": "head_mono",
                          "offset_ns": 100, "max_error_ns": 5, "evidence": evidence("clock")},
        "exposure": {"clock_id": "camera_hw", "time_ns": 1000,
                     "time_basis": "exposure_midpoint", "evidence": evidence("exposure")},
        "head_pose_at_exposure": {"frame_id": "head", "world_frame_id": "local-world-1",
                                  "clock_id": "head_mono", "time_ns": 1100,
                                  "pose_SE3": [1, 2, 3, 0, 0, q, q],
                                  "method": "sampled_at_exposure", "evidence": evidence("head")},
        "sensor_pose_at_exposure": {"frame_id": "left_rgb", "world_frame_id": "local-world-1",
                                    "pose_SE3": [1, 2.1, 3, -0.5, 0.5, 0.5, 0.5]},
    }


def errors(record):
    return validate_camera_authority(record, max_clock_error_ns=5, allow_fixture=True)


def test_schema_is_valid_local_only_and_locked():
    schema = load_camera_authority_schema()
    Draft202012Validator.check_schema(schema)
    text = json.dumps(schema)
    assert '"$ref": "http' not in text
    root = Path(__file__).resolve().parent.parent
    path = "mnesis_canonical/contracts/camera_authority.schema.json"
    lock = json.loads((root / "contracts/contracts.lock").read_text(encoding="utf-8"))
    assert lock["files"][path] == hashlib.sha256((root / path).read_bytes()).hexdigest()


def test_nonidentity_translation_and_rotation_head_preserved():
    record = golden()
    original = copy.deepcopy(record)
    assert errors(record) == []
    sensor = compose_sensor_pose(record, max_clock_error_ns=5, allow_fixture=True)
    assert sensor == pytest.approx([1, 2.1, 3, -0.5, 0.5, 0.5, 0.5])
    assert sensor != record["head_pose_at_exposure"]["pose_SE3"]
    assert record == original  # not head=sensor, not normalized or mutated


def test_actual_json_golden_is_same_authority_and_c1_compatible():
    root = Path(__file__).resolve().parent.parent
    sample = json.loads((root / "examples/camera_authority/nonidentity.fixture.json").read_text(
        encoding="utf-8"))
    assert sample["fixture"] is True
    assert sample["record"] == golden()
    original_head = sample["c1"]["head_pose_SE3"][:]
    assert binding(sample["record"], sample["c1"]) == []
    assert compose_sensor_pose(sample["record"], max_clock_error_ns=5, allow_fixture=True) == (
        pytest.approx(sample["expected_sensor_pose_SE3"]))
    assert sample["c1"]["head_pose_SE3"] == original_head
    assert original_head != sample["expected_sensor_pose_SE3"]
    assert validate_camera_authority(sample["record"], max_clock_error_ns=5)


def test_fixture_default_blocked_and_compose_cannot_bypass():
    record = golden()
    assert any("fixture" in error for error in validate_camera_authority(
        record, max_clock_error_ns=5))
    with pytest.raises(ValueError, match="BLOCKED_CAMERA_AUTHORITY"):
        compose_sensor_pose(record, max_clock_error_ns=5)


@pytest.mark.parametrize("part", ["intrinsics", "clock_mapping", "calibration", "exposure",
                                  "head_pose_at_exposure", "sensor_pose_at_exposure", "provider"])
def test_missing_prerequisite_blocks(part):
    record = golden()
    del record[part]
    assert errors(record)
    with pytest.raises(ValueError, match="BLOCKED_CAMERA_AUTHORITY"):
        compose_sensor_pose(record, max_clock_error_ns=5, allow_fixture=True)


@pytest.mark.parametrize("part,field", [
    ("intrinsics", "K"), ("intrinsics", "calibration_id"),
    ("calibration", "T_head_sensor"), ("calibration", "evidence"),
    ("clock_mapping", "offset_ns"), ("clock_mapping", "max_error_ns"),
    ("exposure", "evidence"), ("head_pose_at_exposure", "evidence"),
])
def test_missing_nested_authority_no_identity_or_clock_fallback(part, field):
    record = golden()
    del record[part][field]
    assert errors(record)


@pytest.mark.parametrize("part,field,value", [
    ("calibration", "sensor_id", "foreign_camera"),
    ("calibration", "head_frame_id", "sensor"),
    ("intrinsics", "calibration_id", "foreign-cal"),
    ("intrinsics", "calibration_revision", "stale-revision"),
    ("head_pose_at_exposure", "world_frame_id", "foreign-world"),
    ("sensor_pose_at_exposure", "world_frame_id", "foreign-world"),
    ("sensor_pose_at_exposure", "frame_id", "head"),
    ("exposure", "clock_id", "host_receipt_clock"),
    ("head_pose_at_exposure", "clock_id", "foreign-clock"),
    ("head_pose_at_exposure", "time_ns", 1000),  # missing offset / stale pose
    ("clock_mapping", "offset_ns", -100),  # inverted mapping direction
    ("clock_mapping", "max_error_ns", 6),
    ("exposure", "time_basis", "host_received_at"),
    ("intrinsics", "model", "distorted_raw"),
])
def test_binding_time_and_geometry_negative(part, field, value):
    record = golden()
    record[part][field] = value
    assert errors(record)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True, 10**500])
def test_bad_pose_numbers_block_not_crash(value):
    record = golden()
    record["head_pose_at_exposure"]["pose_SE3"][0] = value
    assert errors(record)


@pytest.mark.parametrize("field,value", [("width", True), ("K", [0] * 9),
                                        ("K", [400, 1, 320, 0, 400, 240, 0, 0, 1])])
def test_bad_intrinsics(field, value):
    record = golden()
    record["intrinsics"][field] = value
    assert errors(record)


def test_head_cannot_be_copied_to_sensor_or_identity_fabricated():
    record = golden()
    record["sensor_pose_at_exposure"]["pose_SE3"] = record["head_pose_at_exposure"]["pose_SE3"][:]
    assert errors(record)
    record = golden()
    record["calibration"]["T_head_sensor"] = [0, 0, 0, 0, 0, 0, 1]
    assert errors(record)


def test_explicit_identity_is_not_missing_and_still_needs_evidence():
    record = golden()
    record["calibration"]["T_head_sensor"] = [0, 0, 0, 0, 0, 0, 1]
    record["sensor_pose_at_exposure"]["pose_SE3"] = record["head_pose_at_exposure"]["pose_SE3"][:]
    assert errors(record) == []  # only synthetic explicit calibration, not runtime truth
    del record["calibration"]["evidence"]
    assert errors(record)


def test_unit_quaternion_and_sign_equivalence():
    record = golden()
    record["sensor_pose_at_exposure"]["pose_SE3"][3:] = [0.5, -0.5, -0.5, -0.5]
    assert errors(record) == []
    record["head_pose_at_exposure"]["pose_SE3"][6] = 2
    assert errors(record)


@pytest.mark.parametrize("part,field", [
    ("head_pose_at_exposure", "pose_SE3"), ("calibration", "T_head_sensor"),
    ("sensor_pose_at_exposure", "pose_SE3"),
])
def test_finite_giant_quaternion_blocks_without_overflow(part, field):
    record = golden()
    record[part][field][3] = 10**200
    assert errors(record)
    with pytest.raises(ValueError, match="BLOCKED_CAMERA_AUTHORITY"):
        compose_sensor_pose(record, max_clock_error_ns=5, allow_fixture=True)


@pytest.mark.parametrize("budget", [True, -1, None, 5.0])
def test_unknown_or_invalid_clock_policy_blocks(budget):
    assert validate_camera_authority(golden(), max_clock_error_ns=budget, allow_fixture=True)


def test_no_ambient_same_clock_or_control_character():
    record = golden()
    record["clock_mapping"]["source_clock_id"] = "head_mono"
    record["exposure"]["clock_id"] = "head_mono"
    assert errors(record)
    record = golden()
    record["calibration"]["evidence"]["ref"] = "calibration.json\n"
    assert errors(record)


def test_unknown_fields_and_versions_fail_closed():
    record = golden()
    record["ready"] = True
    assert errors(record)
    record = golden()
    record["schema_version"] = "c2/1.0"
    assert errors(record)


class BindingDefault(Enum):
    GOLDEN = "golden"


def binding(
    record, frame, *, episode_id: str = "fixture-episode", image_sha256: str = "a" * 64,
    calibration_revision: str = "fixture-r1",
    calibration_sha256: str = hashlib.sha256(b"calibration").hexdigest(),
    calibrated_T_head_sensor: list[float] | BindingDefault = BindingDefault.GOLDEN,
    calibrated_intrinsics: dict[str, object] | BindingDefault = BindingDefault.GOLDEN,
    provider_id: str = "synthetic-provider", provider_version: str = "fixture-v1",
    max_clock_error_ns: int = 5, allow_fixture: bool = True,
):
    return validate_camera_authority_binding(
        record, frame=frame, episode_id=episode_id, image_sha256=image_sha256,
        calibration_revision=calibration_revision, calibration_sha256=calibration_sha256,
        calibrated_T_head_sensor=(golden()["calibration"]["T_head_sensor"]
                                  if calibrated_T_head_sensor is BindingDefault.GOLDEN
                                  else calibrated_T_head_sensor),
        calibrated_intrinsics=(golden()["intrinsics"]
                               if calibrated_intrinsics is BindingDefault.GOLDEN
                               else calibrated_intrinsics),
        provider_id=provider_id, provider_version=provider_version,
        max_clock_error_ns=max_clock_error_ns, allow_fixture=allow_fixture,
    )


def test_c1_binding_keeps_actual_head_pose_and_validates_c1(good_frame):
    frame = good_frame()
    frame["frame_index"] = 7
    frame["observation.images.ego"] = "frames/000007.jpg"
    original = copy.deepcopy(frame)
    assert binding(golden(), frame) == []
    assert frame == original
    # head identity is the real C1 fixture row value, not the exposure sensor pose.
    assert frame["head_pose_SE3"] != golden()["sensor_pose_at_exposure"]["pose_SE3"]
    del frame["head_pose_SE3"]
    assert binding(golden(), frame)


@pytest.mark.parametrize("field,value", [
    ("episode_id", "foreign-episode"), ("image_sha256", "b" * 64),
    ("calibration_revision", "old-r0"), ("calibration_sha256", "c" * 64),
    ("calibrated_T_head_sensor", [0, 0, 0, 0, 0, 0, 1]),
    ("calibrated_intrinsics", {}),
    ("provider_id", "foreign-provider"), ("provider_version", "old-fixture-v0"),
])
def test_consumer_verified_join_mismatch(good_frame, field, value):
    frame = good_frame()
    frame["frame_index"] = 7
    frame["observation.images.ego"] = "frames/000007.jpg"
    assert binding(golden(), frame, **{field: value})


@pytest.mark.parametrize("field,value", [
    ("calibrated_T_head_sensor", None), ("calibrated_intrinsics", None),
])
def test_explicit_none_calibration_override_is_not_defaulted(good_frame, field, value):
    frame = good_frame()
    frame["frame_index"] = 7
    frame["observation.images.ego"] = "frames/000007.jpg"
    assert binding(golden(), frame, **{field: value})


@pytest.mark.parametrize("field,value", [
    ("frame_index", 8), ("observation.images.ego", "frames/foreign.jpg"),
])
def test_c1_image_frame_join_mismatch(good_frame, field, value):
    frame = good_frame()
    frame["frame_index"] = 7
    frame["observation.images.ego"] = "frames/000007.jpg"
    frame[field] = value
    assert binding(golden(), frame)


def test_image_key_mismatch_and_nonvisual_cannot_get_visual_authority(good_frame):
    frame = good_frame()
    frame["frame_index"] = 7
    frame["observation.images.ego"] = "frames/000007.jpg"
    record = golden()
    record["image_key"] = "observation.images.foreign"
    assert binding(record, frame)
    frame["profile"] = "robot_v2"
    del frame["observation.images.ego"]
    assert binding(golden(), frame)
