"""Conformance for the contracts/ mirror + lock (v1.6 camera-control + v1.7 WebRTC signaling).

The camera-control negotiation and video-capability declaration are wire-level
C3 (xr_bridge) additions whose reference implementation lives in the consumer
repos (Daedalus/Eidolon); on the canonical side they are specified in the
contract markdown. WebRTC signaling messages (video_offer/answer/ice) are
v1.7 additive extensions.

These tests pin the spec text so the contract stays coherent and the lock stays
in sync.
"""
from __future__ import annotations

from pathlib import Path

from mnesis_canonical import contracts_check

CONTRACTS = Path(__file__).resolve().parent.parent / "contracts"
REPO_ROOT = Path(__file__).resolve().parent.parent
XR_CONTRACT = (CONTRACTS / "XR_ROBOT_CONTRACT.md").read_text(encoding="utf-8")
XR_SPEC = (CONTRACTS / "xr_bridge_SPEC.md").read_text(encoding="utf-8")
SPEC_TEXT = (REPO_ROOT / "SPEC.md").read_text(encoding="utf-8")
REFERENCE_TEXT = (CONTRACTS / "canonical_frame_schema_REFERENCE.md").read_text(encoding="utf-8")


def test_contracts_lock_integrity():
    """contracts.lock must match the files on disk (regenerate if this fails)."""
    assert contracts_check.cmd_verify() == 0


def test_c3_bumped_to_v1_7():
    assert "**版本**: v1.7" in XR_CONTRACT
    assert "**版本**: v1.7" in XR_SPEC


def test_c3_camera_control_message_specified():
    for text in (XR_CONTRACT, XR_SPEC):
        assert "C3_CameraControl" in text
        assert "C3_CameraStatus" in text
    # negotiation payload fields (OPEN_CAMERA-style over our ws envelope)
    for field in ("camera_id", "width", "height", "fps", "bitrate", "codec"):
        assert field in XR_CONTRACT


def test_c3_video_capabilities_declared():
    for text in (XR_CONTRACT, XR_SPEC):
        assert "video_capabilities" in text
    # webrtc|mjpeg feature negotiation, reserved for the DQ-1 WebRTC line
    assert "webrtc" in XR_CONTRACT and "mjpeg" in XR_CONTRACT
    assert "transports" in XR_CONTRACT


def test_c3_additions_are_backward_compatible():
    # Both v1.6 and v1.7 additions must be documented as additive
    assert "additive" in XR_CONTRACT
    assert "v1.5" in XR_CONTRACT  # v1.6 backward-compat clause references older clients
    assert "v1.6" in XR_CONTRACT  # v1.7 backward-compat clause references older clients


def test_webrtc_signaling_messages_specified():
    """v1.7 WebRTC signaling messages must appear in both contract and spec."""
    for text in (XR_CONTRACT, XR_SPEC):
        assert "video_offer" in text
        assert "video_answer" in text
        assert "video_ice" in text


def test_webrtc_multi_subscriber_fields():
    """stream_id and subscriber_id must be specified for multi-subscriber support."""
    assert "stream_id" in XR_CONTRACT
    assert "subscriber_id" in XR_CONTRACT
    for text in (XR_CONTRACT, XR_SPEC):
        assert "stream_id" in text
        assert "subscriber_id" in text


def test_webrtc_qos_hint_specified():
    """qos_hint with low_latency/stable values must be documented."""
    assert "qos_hint" in XR_CONTRACT
    assert "low_latency" in XR_CONTRACT
    assert "stable" in XR_CONTRACT


def test_webrtc_backward_compatible():
    """v1.7 WebRTC additions must be documented as additive/ignorable by <=v1.6 clients."""
    assert "v1.7" in XR_CONTRACT
    # ≤v1.6 clients ignore video_* messages, fall back to MJPEG
    assert "MJPEG" in XR_CONTRACT or "mjpeg" in XR_CONTRACT


def test_webrtc_signaling_schema_exists():
    """webrtc_signaling.schema.json must exist and be tracked by the lock."""
    schema_path = CONTRACTS / "webrtc_signaling.schema.json"
    assert schema_path.exists(), "webrtc_signaling.schema.json must exist"
    # Verify it's tracked in contracts.lock
    lock = contracts_check._load_lock()
    assert lock is not None
    assert "webrtc_signaling.schema.json" in lock.get("files", {})


def test_version_history_mentions_issue_60():
    """v1.7 version history must reference issue #60."""
    assert "issue #60" in XR_CONTRACT or "#60" in XR_CONTRACT


# ── Gripper direction consistency (regression: issue #73) ──────────────────────


def _find_gripper_rows(text: str) -> list[str]:
    """Return spec table rows mentioning ``observation.gripper``."""
    # Match table rows (pipe-delimited) that contain "observation.gripper"
    rows = []
    for line in text.splitlines():
        if line.startswith("|") and "observation.gripper" in line:
            rows.append(line.strip())
    return rows


def test_gripper_direction_consistent_in_spec():
    """SPEC.md must not contain the opposite-direction PR#39 residue.

    The canonical direction is ``0.0 = fully open, 1.0 = fully closed``.
    No table row or prose paragraph shall define ``observation.gripper``
    with ``0 = closed`` or ``0=闭合`` (the old C8 direction).
    """
    # The old C8 direction phrases we must NOT find anywhere in SPEC.md
    forbidden = [
        "0=closed, 1=open",
        "0=闭合，1=张开",
        # The exact C8 table row patterns (now deleted)
        "C8 gripper opening",
        "C8 left gripper opening",
        "C8 right gripper opening",
    ]
    for pattern in forbidden:
        assert pattern not in SPEC_TEXT, (
            f"SPEC.md must not contain the old C8 direction: {pattern!r}"
        )

    # Verify the correct direction is present instead
    assert "0.0` = fully open, `1.0` = fully closed" in SPEC_TEXT, (
        "SPEC.md must define the canonical gripper direction"
    )


def test_gripper_direction_consistent_in_reference():
    """canonical_frame_schema_REFERENCE.md must not contain the PR#39 residue.

    The same three C8 rows and the C8 additive header must be absent.
    """
    forbidden = [
        "C8 夹爪开度",
        "C8 左夹爪开度",
        "C8 右夹爪开度",
        "C8 夹爪通道",
    ]
    for pattern in forbidden:
        assert pattern not in REFERENCE_TEXT, (
            f"REFERENCE.md must not contain the old C8 direction: {pattern!r}"
        )

    # Verify the correct direction is present instead
    assert "0.0`=完全张开 / `1.0`=完全闭合" in REFERENCE_TEXT, (
        "REFERENCE.md must define the canonical gripper direction"
    )


def test_no_duplicate_observation_gripper_rows_in_spec():
    """Every observation.gripper key must appear at most once in the SPEC field table.

    Regression guard for issue #73 — the same key appearing twice with
    opposite directions must never recur.
    """
    rows = _find_gripper_rows(SPEC_TEXT)
    seen: dict[str, int] = {}
    for row in rows:
        # Extract the key from the second pipe-delimited column
        parts = [p.strip() for p in row.split("|")]
        if len(parts) >= 2:
            key = parts[1]
            seen[key] = seen.get(key, 0) + 1

    duplicates = {k: v for k, v in seen.items() if v > 1}
    assert not duplicates, (
        f"Duplicate observation.gripper rows in SPEC.md field table: {duplicates}"
    )


def test_no_duplicate_observation_gripper_rows_in_reference():
    """Every observation.gripper key must appear at most once in the REFERENCE
    field table."""
    rows = _find_gripper_rows(REFERENCE_TEXT)
    seen: dict[str, int] = {}
    for row in rows:
        parts = [p.strip() for p in row.split("|")]
        if len(parts) >= 2:
            key = parts[1]
            seen[key] = seen.get(key, 0) + 1

    duplicates = {k: v for k, v in seen.items() if v > 1}
    assert not duplicates, (
        f"Duplicate observation.gripper rows in REFERENCE.md field table: {duplicates}"
    )
