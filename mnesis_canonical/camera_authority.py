"""C9 camera authority: explicit exposure clock and calibrated head-to-sensor pose.

Validation qualifies supplied evidence bindings, not physical truth. This module
does not read images, evidence paths, devices or services; consumers verify those
receipts separately. No identity/clock/intrinsics fallback is permitted.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "camera-authority/1.0"
SCHEMA_PATH = Path(__file__).parent / "contracts" / "camera_authority.schema.json"


def load_camera_authority_schema() -> dict[str, Any]:
    """Load the bundled, standalone authority contract (not a C1 extension)."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _finite_numbers(value: Any) -> bool:
    if isinstance(value, dict):
        return all(_finite_numbers(item) for item in value.values())
    if isinstance(value, list):
        return all(_finite_numbers(item) for item in value)
    if type(value) in (int, float):
        try:
            return math.isfinite(value)
        except OverflowError:
            return False
    if isinstance(value, str):
        return not any(ord(char) < 32 for char in value)
    return True


def _quaternion_product(a: list[float], b: list[float]) -> list[float]:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return [
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    ]


def _compose(head: list[float], extrinsic: list[float]) -> list[float]:
    q = head[3:]
    rotated = _quaternion_product(
        _quaternion_product(q, [*extrinsic[:3], 0.0]),
        [-q[0], -q[1], -q[2], q[3]],
    )
    return [head[i] + rotated[i] for i in range(3)] + _quaternion_product(q, extrinsic[3:])


def validate_camera_authority(
    record: Any, *, max_clock_error_ns: int, allow_fixture: bool = False
) -> list[str]:
    """Return qualification errors; missing prerequisites are blocking errors.

    The caller must provide its own finite integer clock-uncertainty budget.
    Success is NOT a device, calibration, C1 join or reconstruction receipt.
    Synthetic evidence is rejected unless allow_fixture=True explicitly; that
    opt-in is for CPU fixtures only and must never qualify reconstruction.
    The JSON Schema checks structure; these checks add cross-field pose/time
    semantics. Both are required. jsonschema is the existing optional dependency.
    """
    if type(max_clock_error_ns) is not int or max_clock_error_ns < 0:
        return ["policy.max_clock_error_ns: required nonnegative integer (not bool)"]
    if not _finite_numbers(record):
        return ["record: non-finite numbers or control characters are forbidden"]
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return ["validator: jsonschema unavailable; authority remains blocked"]
    schema = load_camera_authority_schema()
    errors = [
        f"{'.'.join(str(part) for part in error.absolute_path) or 'record'}: {error.message}"
        for error in Draft202012Validator(schema).iter_errors(record)
    ]
    if errors:
        return errors

    calibration = record["calibration"]
    clock = record["clock_mapping"]
    exposure = record["exposure"]
    head = record["head_pose_at_exposure"]
    sensor = record["sensor_pose_at_exposure"]
    if type(allow_fixture) is not bool:
        return ["policy.allow_fixture: must be a boolean"]
    if not allow_fixture and any(
        part["evidence"]["fixture"]
        for part in (calibration, clock, exposure, head, record["provider"])
    ):
        errors.append("evidence.fixture: fixture cannot qualify runtime camera authority")
    if calibration["sensor_id"] != record["sensor_id"]:
        errors.append("calibration.sensor_id: differs from observed sensor")
    if head["frame_id"] != calibration["head_frame_id"]:
        errors.append("head_pose_at_exposure.frame_id: differs from calibration head frame")
    if record["intrinsics"]["calibration_id"] != calibration["calibration_id"]:
        errors.append("intrinsics.calibration_id: differs from extrinsic calibration")
    if record["intrinsics"]["calibration_revision"] != calibration["revision"]:
        errors.append("intrinsics.calibration_revision: differs from extrinsic revision")
    if head["world_frame_id"] != record["world_frame_id"]:
        errors.append("head_pose_at_exposure.world_frame_id: differs from record world frame")
    if sensor["world_frame_id"] != record["world_frame_id"]:
        errors.append("sensor_pose_at_exposure.world_frame_id: differs from record world frame")
    if sensor["frame_id"] != record["sensor_id"]:
        errors.append("sensor_pose_at_exposure.frame_id: differs from observed sensor")
    if exposure["clock_id"] != clock["source_clock_id"]:
        errors.append("exposure.clock_id: differs from clock mapping source")
    if head["clock_id"] != clock["target_clock_id"]:
        errors.append("head_pose_at_exposure.clock_id: differs from clock mapping target")
    # Mapping direction is explicit: target = source + offset, not +/- guessing.
    if head["time_ns"] != exposure["time_ns"] + clock["offset_ns"]:
        errors.append("head_pose_at_exposure.time_ns: not mapped exposure time")
    if clock["source_clock_id"] == clock["target_clock_id"] and clock["offset_ns"] != 0:
        errors.append("clock_mapping.offset_ns: same clock namespace requires zero offset")
    if clock["max_error_ns"] > max_clock_error_ns:
        errors.append("clock_mapping.max_error_ns: exceeds consumer policy budget")
    k = record["intrinsics"]["K"]
    if k[0] <= 0 or k[4] <= 0 or k[1] != 0 or k[3] != 0 or k[6:] != [0, 0, 1]:
        errors.append("intrinsics.K: expected finite pinhole [fx,0,cx,0,fy,cy,0,0,1]")
    poses = {
        "head_pose_at_exposure.pose_SE3": head["pose_SE3"],
        "calibration.T_head_sensor": calibration["T_head_sensor"],
        "sensor_pose_at_exposure.pose_SE3": sensor["pose_SE3"],
    }
    for name, pose in poses.items():
        # Reject an impossible unit component BEFORE mixing giant ints/floats in
        # sum(n*n): that addition itself can overflow, before a norm check runs.
        if any(abs(n) > 1 + 1e-9 for n in pose[3:]):
            errors.append(f"{name}: quaternion component outside unit range")
            continue
        norm_squared = sum(n * n for n in pose[3:])
        if not _finite_numbers(norm_squared) or not math.isclose(
            norm_squared, 1.0, rel_tol=0, abs_tol=1e-9
        ):
            errors.append(f"{name}: quaternion must be unit; no silent normalization")
    if errors:
        return errors
    expected = _compose(head["pose_SE3"], calibration["T_head_sensor"])
    if not _finite_numbers(expected):
        return ["sensor_pose_at_exposure.pose_SE3: composition is non-finite"]
    actual = sensor["pose_SE3"]
    translation_matches = all(
        math.isclose(expected[i], actual[i], rel_tol=0, abs_tol=1e-9) for i in range(3)
    )
    # q and -q represent the same orientation; translation never inherits that sign.
    rotation_matches = any(
        all(math.isclose(expected[i], sign * actual[i], rel_tol=0, abs_tol=1e-9)
            for i in range(3, 7))
        for sign in (1, -1)
    )
    if not translation_matches or not rotation_matches:
        errors.append("sensor_pose_at_exposure.pose_SE3: violates T_world_head * T_head_sensor")
    return errors


def validate_camera_authority_binding(
    record: Any, *, frame: Any, episode_id: str, image_sha256: str,
    calibration_revision: str, calibration_sha256: str, max_clock_error_ns: int,
    calibrated_T_head_sensor: list[float], calibrated_intrinsics: dict[str, Any],
    provider_id: str, provider_version: str,
    allow_fixture: bool = False,
) -> list[str]:
    """Bind authority to a C1 row and independently verified image/calibration hashes.

    episode_id is the upload's identity: C1 itself has episode_index, not UUID.
    Hash/revision arguments must come from consumer-verified bytes/registry, not
    be echoed from the record. This function performs no I/O or defaulting.
    C1 head pose is intentionally not overwritten/equated to a non-reference
    camera's exposure-time pose; different camera exposure times can differ.
    """
    errors = validate_camera_authority(
        record, max_clock_error_ns=max_clock_error_ns, allow_fixture=allow_fixture
    )
    if errors:
        return errors
    if not isinstance(frame, dict):
        return ["frame: expected C1 object"]
    from .validate import validate_frame

    errors.extend(f"frame: {error}" for error in validate_frame(frame))
    if episode_id != record["episode_id"]:
        errors.append("episode_id: authority differs from upload identity")
    if type(frame.get("frame_index")) is not int or frame["frame_index"] != record["frame_index"]:
        errors.append("frame_index: authority differs from C1 row")
    if frame.get(record["image_key"]) != record["image_ref"]:
        errors.append("image_key/image_ref: authority differs from C1 image")
    if image_sha256 != record["image_sha256"]:
        errors.append("image_sha256: authority differs from consumer-verified bytes")
    calibration = record["calibration"]
    if calibration_revision != calibration["revision"]:
        errors.append("calibration.revision: differs from consumer-verified registry")
    if calibration_sha256 != calibration["evidence"]["sha256"]:
        errors.append("calibration.evidence.sha256: differs from consumer-verified bytes")
    if calibrated_T_head_sensor != calibration["T_head_sensor"]:
        errors.append("calibration.T_head_sensor: differs from consumer-verified calibration")
    if calibrated_intrinsics != record["intrinsics"]:
        errors.append("intrinsics: differs from consumer-verified calibration")
    if provider_id != record["provider"]["id"] or provider_version != record["provider"]["version"]:
        errors.append("provider.id/version: differs from consumer-verified provider")
    return errors


def compose_sensor_pose(
    record: Any, *, max_clock_error_ns: int, allow_fixture: bool = False
) -> list[float]:
    """Return the qualified composition, never replacing or mutating the head pose."""
    errors = validate_camera_authority(
        record, max_clock_error_ns=max_clock_error_ns, allow_fixture=allow_fixture
    )
    if errors:
        raise ValueError("BLOCKED_CAMERA_AUTHORITY: " + "; ".join(errors))
    return _compose(record["head_pose_at_exposure"]["pose_SE3"],
                    record["calibration"]["T_head_sensor"])
