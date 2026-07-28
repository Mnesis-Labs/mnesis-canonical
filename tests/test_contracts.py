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
XR_CONTRACT = (CONTRACTS / "XR_ROBOT_CONTRACT.md").read_text(encoding="utf-8")
XR_SPEC = (CONTRACTS / "xr_bridge_SPEC.md").read_text(encoding="utf-8")


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