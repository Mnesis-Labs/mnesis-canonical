"""Conformance for the contracts/ mirror + lock (D-18 C3 v1.6 additions).

The camera-control negotiation and video-capability declaration are wire-level
C3 (xr_bridge) additions whose reference implementation lives in the consumer
repos (Daedalus/Eidolon); on the canonical side they are specified in the
contract markdown. These tests pin the spec text so the contract stays coherent
and the lock stays in sync.
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


def test_c3_bumped_to_v1_6():
    assert "**版本**: v1.6" in XR_CONTRACT
    assert "**版本**: v1.6" in XR_SPEC


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
    # v1.6 additions must be documented as additive / ignorable by <=v1.5 clients
    assert "additive" in XR_CONTRACT
    assert "v1.5" in XR_CONTRACT  # backward-compat clause references older clients
