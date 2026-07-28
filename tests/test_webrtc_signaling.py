"""Conformance tests for the WebRTC signaling JSON Schema (C3 v1.7).

Tests validate messages against ``contracts/webrtc_signaling.schema.json``
covering the standard WS envelope {type, seq, ts, body} with body-specific
validation for video_offer, video_answer, and video_ice.

Positive cases:
  - Each message type with all required fields
  - Multi-subscriber scenario (two different subscriber_ids, same stream_id)
  - Optional fields (qos_hint, codec, resolution, message)
  - Tricle ICE (candidate sent before answer available)

Negative cases:
  - Missing required fields (stream_id, subscriber_id, sdp, candidate, etc.)
  - Wrong field types
  - Invalid enum values for qos_hint
  - Empty strings for required fields
  - Additional properties (should be rejected by schema)
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "contracts" / "webrtc_signaling.schema.json"
SDP = "v=0\no=- 1 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)


def _validate(msg: dict) -> list[str]:
    """Return list of validation error messages (empty = valid)."""
    return [err.message for err in sorted(VALIDATOR.iter_errors(msg), key=str)]


# ---------------------------------------------------------------------------
# Positive cases
# ---------------------------------------------------------------------------


def test_video_offer_positive():
    """A valid video_offer with all required fields passes."""
    msg = {
        "type": "video_offer",
        "seq": 1,
        "ts": 1712345678000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "sdp": SDP,
        },
    }
    assert _validate(msg) == []


def test_video_answer_positive():
    """A valid video_answer with all required fields passes."""
    msg = {
        "type": "video_answer",
        "seq": 2,
        "ts": 1712345679000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "sdp": SDP,
            "accepted": True,
        },
    }
    assert _validate(msg) == []


def test_video_ice_positive():
    """A valid video_ice with all required fields passes."""
    msg = {
        "type": "video_ice",
        "seq": 3,
        "ts": 1712345680000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "candidate": "candidate:1 1 UDP 2122252543 192.168.1.100 49152 typ host",
            "sdp_mid": "0",
            "sdp_mline_index": 0,
        },
    }
    assert _validate(msg) == []


def test_video_offer_with_optional_fields():
    """video_offer with all optional fields (qos_hint, codec, resolution) passes."""
    msg = {
        "type": "video_offer",
        "seq": 10,
        "ts": 1712345678000000000,
        "body": {
            "stream_id": "camera_wrist_left",
            "subscriber_id": "quest_2",
            "sdp": "v=0\no=- 111 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
            "qos_hint": "low_latency",
            "codec": "h264",
            "width": 1280,
            "height": 720,
        },
    }
    assert _validate(msg) == []


def test_video_answer_with_optional_fields():
    """video_answer with optional qos_hint and message passes."""
    msg = {
        "type": "video_answer",
        "seq": 11,
        "ts": 1712345679000000000,
        "body": {
            "stream_id": "camera_wrist_left",
            "subscriber_id": "quest_2",
            "sdp": "v=0\no=- 222 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
            "accepted": True,
            "qos_hint": "low_latency",
            "message": "codec h264 accepted, 1280x720@30fps",
        },
    }
    assert _validate(msg) == []


def test_video_answer_rejected():
    """video_answer with accepted=false and message passes."""
    msg = {
        "type": "video_answer",
        "seq": 12,
        "ts": 1712345679000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "sdp": "v=0\no=- 333 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
            "accepted": False,
            "message": "codec unsupported, falling back to mjpeg",
        },
    }
    assert _validate(msg) == []


def test_video_ice_trickle():
    """video_ice sent before answer (Trickle ICE semantics) is valid."""
    msg = {
        "type": "video_ice",
        "seq": 5,
        "ts": 1712345680000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "candidate": "candidate:2 1 UDP 2122252543 192.168.1.101 49153 typ host",
            "sdp_mid": "0",
            "sdp_mline_index": 0,
        },
    }
    assert _validate(msg) == []


def test_multi_subscriber_offer_scenario():
    """Two different subscriber_ids for the same stream_id are both valid.

    This tests the core multi-subscriber scenario: Web and Quest both
    subscribing to the same video stream.
    """
    web_offer = {
        "type": "video_offer",
        "seq": 1,
        "ts": 1712345678000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "sdp": "v=0\no=- 101 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
        },
    }
    quest_offer = {
        "type": "video_offer",
        "seq": 1,
        "ts": 1712345678000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "quest_2",
            "sdp": "v=0\no=- 201 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
        },
    }
    assert _validate(web_offer) == []
    assert _validate(quest_offer) == []


def test_multi_subscriber_answer_scenario():
    """Two different subscriber_ids receive answers for the same stream_id."""
    web_answer = {
        "type": "video_answer",
        "seq": 100,
        "ts": 1712345679000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "sdp": "v=0\no=- 102 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
            "accepted": True,
        },
    }
    quest_answer = {
        "type": "video_answer",
        "seq": 200,
        "ts": 1712345679000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "quest_2",
            "sdp": "v=0\no=- 202 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
            "accepted": True,
        },
    }
    assert _validate(web_answer) == []
    assert _validate(quest_answer) == []


def test_multi_subscriber_ice_scenario():
    """ICE candidates for different subscriber_ids are both valid."""
    web_ice = {
        "type": "video_ice",
        "seq": 101,
        "ts": 1712345680000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "candidate": "candidate:1 1 UDP 2122252543 10.0.0.1 49152 typ host",
            "sdp_mid": "0",
            "sdp_mline_index": 0,
        },
    }
    quest_ice = {
        "type": "video_ice",
        "seq": 201,
        "ts": 1712345680000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "quest_2",
            "candidate": "candidate:1 1 UDP 2122252543 10.0.0.2 49153 typ host",
            "sdp_mid": "0",
            "sdp_mline_index": 0,
        },
    }
    assert _validate(web_ice) == []
    assert _validate(quest_ice) == []


def test_qos_hint_stable():
    """qos_hint 'stable' is a valid enum value."""
    msg = {
        "type": "video_offer",
        "seq": 1,
        "ts": 1712345678000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "default",
            "sdp": "v=0\no=- 1 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
            "qos_hint": "stable",
        },
    }
    assert _validate(msg) == []


# ---------------------------------------------------------------------------
# Negative cases — missing required fields
# ---------------------------------------------------------------------------


def test_video_offer_missing_stream_id():
    msg = {
        "type": "video_offer",
        "seq": 1,
        "ts": 1712345678000000000,
        "body": {
            "subscriber_id": "web_dashboard_1",
            "sdp": "v=0\no=- 1 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
        },
    }
    errs = _validate(msg)
    assert errs, "Expected validation error for missing stream_id"


def test_video_offer_missing_subscriber_id():
    msg = {
        "type": "video_offer",
        "seq": 1,
        "ts": 1712345678000000000,
        "body": {
            "stream_id": "camera_head",
            "sdp": "v=0\no=- 1 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
        },
    }
    errs = _validate(msg)
    assert errs, "Expected validation error for missing subscriber_id"


def test_video_offer_missing_sdp():
    msg = {
        "type": "video_offer",
        "seq": 1,
        "ts": 1712345678000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
        },
    }
    errs = _validate(msg)
    assert errs, "Expected validation error for missing sdp"


def test_video_answer_missing_accepted():
    msg = {
        "type": "video_answer",
        "seq": 2,
        "ts": 1712345679000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "sdp": "v=0\no=- 1 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
        },
    }
    errs = _validate(msg)
    assert errs, "Expected validation error for missing accepted"


def test_video_ice_missing_candidate():
    msg = {
        "type": "video_ice",
        "seq": 3,
        "ts": 1712345680000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "sdp_mid": "0",
            "sdp_mline_index": 0,
        },
    }
    errs = _validate(msg)
    assert errs, "Expected validation error for missing candidate"


def test_video_ice_missing_sdp_mid():
    msg = {
        "type": "video_ice",
        "seq": 3,
        "ts": 1712345680000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "candidate": "candidate:1 1 UDP 2122252543 192.168.1.100 49152 typ host",
            "sdp_mline_index": 0,
        },
    }
    errs = _validate(msg)
    assert errs, "Expected validation error for missing sdp_mid"


def test_video_ice_missing_sdp_mline_index():
    msg = {
        "type": "video_ice",
        "seq": 3,
        "ts": 1712345680000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "candidate": "candidate:1 1 UDP 2122252543 192.168.1.100 49152 typ host",
            "sdp_mid": "0",
        },
    }
    errs = _validate(msg)
    assert errs, "Expected validation error for missing sdp_mline_index"


# ---------------------------------------------------------------------------
# Negative cases — wrong field types
# ---------------------------------------------------------------------------


def test_video_offer_stream_id_not_string():
    msg = {
        "type": "video_offer",
        "seq": 1,
        "ts": 1712345678000000000,
        "body": {
            "stream_id": 123,
            "subscriber_id": "web_dashboard_1",
            "sdp": "v=0\no=- 1 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
        },
    }
    errs = _validate(msg)
    assert errs, "Expected validation error for non-string stream_id"


def test_video_offer_empty_stream_id():
    msg = {
        "type": "video_offer",
        "seq": 1,
        "ts": 1712345678000000000,
        "body": {
            "stream_id": "",
            "subscriber_id": "web_dashboard_1",
            "sdp": "v=0\no=- 1 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
        },
    }
    errs = _validate(msg)
    assert errs, "Expected validation error for empty stream_id"


def test_video_offer_empty_subscriber_id():
    msg = {
        "type": "video_offer",
        "seq": 1,
        "ts": 1712345678000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "",
            "sdp": "v=0\no=- 1 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
        },
    }
    errs = _validate(msg)
    assert errs, "Expected validation error for empty subscriber_id"


def test_video_offer_empty_sdp():
    msg = {
        "type": "video_offer",
        "seq": 1,
        "ts": 1712345678000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "sdp": "",
        },
    }
    errs = _validate(msg)
    assert errs, "Expected validation error for empty sdp"


def test_video_answer_accepted_not_bool():
    msg = {
        "type": "video_answer",
        "seq": 2,
        "ts": 1712345679000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "sdp": "v=0\no=- 1 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
            "accepted": "true",
        },
    }
    errs = _validate(msg)
    assert errs, "Expected validation error for non-boolean accepted"


def test_video_ice_sdp_mline_index_not_int():
    msg = {
        "type": "video_ice",
        "seq": 3,
        "ts": 1712345680000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "candidate": "candidate:1 1 UDP 2122252543 192.168.1.100 49152 typ host",
            "sdp_mid": "0",
            "sdp_mline_index": "0",
        },
    }
    errs = _validate(msg)
    assert errs, "Expected validation error for non-integer sdp_mline_index"


def test_video_ice_negative_sdp_mline_index():
    msg = {
        "type": "video_ice",
        "seq": 3,
        "ts": 1712345680000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "candidate": "candidate:1 1 UDP 2122252543 192.168.1.100 49152 typ host",
            "sdp_mid": "0",
            "sdp_mline_index": -1,
        },
    }
    errs = _validate(msg)
    assert errs, "Expected validation error for negative sdp_mline_index"


# ---------------------------------------------------------------------------
# Negative cases — invalid enum values
# ---------------------------------------------------------------------------


def test_video_offer_invalid_qos_hint():
    msg = {
        "type": "video_offer",
        "seq": 1,
        "ts": 1712345678000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "sdp": "v=0\no=- 1 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
            "qos_hint": "ultra_low_latency",
        },
    }
    errs = _validate(msg)
    assert errs, "Expected validation error for invalid qos_hint enum value"


def test_video_answer_invalid_qos_hint():
    msg = {
        "type": "video_answer",
        "seq": 2,
        "ts": 1712345679000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "sdp": "v=0\no=- 1 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
            "accepted": True,
            "qos_hint": "balanced",
        },
    }
    errs = _validate(msg)
    assert errs, "Expected validation error for invalid qos_hint enum value"


# ---------------------------------------------------------------------------
# Negative cases — wrong top-level type for the message body
# ---------------------------------------------------------------------------


def test_unknown_type_rejected():
    """A message with an unknown type (not in the enum) is rejected."""
    msg = {
        "type": "video_unknown",
        "seq": 1,
        "ts": 1712345678000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "sdp": "v=0\no=- 1 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
        },
    }
    errs = _validate(msg)
    assert errs, "Expected validation error for unknown type"


# ---------------------------------------------------------------------------
# Negative cases — additional properties (schema sets additionalProperties: false)
# ---------------------------------------------------------------------------


def test_video_offer_additional_property():
    msg = {
        "type": "video_offer",
        "seq": 1,
        "ts": 1712345678000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "sdp": "v=0\no=- 1 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
            "extra_field": "should_not_be_here",
        },
    }
    errs = _validate(msg)
    assert errs, "Expected validation error for extra property in body"


# ---------------------------------------------------------------------------
# Edge cases — V2 reserved fields
# ---------------------------------------------------------------------------


def test_video_offer_v2_reserved_fields():
    """V2 reserved fields (width, height, codec) are accepted when present."""
    msg = {
        "type": "video_offer",
        "seq": 1,
        "ts": 1712345678000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "sdp": "v=0\no=- 1 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
            "codec": "h265",
            "width": 3840,
            "height": 2160,
        },
    }
    assert _validate(msg) == []


def test_video_offer_none_width_rejected():
    """width must be a positive integer, not null."""
    msg = {
        "type": "video_offer",
        "seq": 1,
        "ts": 1712345678000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "sdp": "v=0\no=- 1 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
            "width": None,
        },
    }
    errs = _validate(msg)
    assert errs, "Expected validation error for null width"


def test_video_offer_width_zero_rejected():
    """width must be >= 1."""
    msg = {
        "type": "video_offer",
        "seq": 1,
        "ts": 1712345678000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "sdp": "v=0\no=- 1 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
            "width": 0,
        },
    }
    errs = _validate(msg)
    assert errs, "Expected validation error for width=0"


# ---------------------------------------------------------------------------
# Edge cases — single subscriber (default subscriber_id)
# ---------------------------------------------------------------------------


def test_single_subscriber_default_id():
    """Single subscriber scenario uses 'default' as subscriber_id — must be valid."""
    msg = {
        "type": "video_offer",
        "seq": 1,
        "ts": 1712345678000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "default",
            "sdp": "v=0\no=- 1 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
        },
    }
    assert _validate(msg) == []


# ---------------------------------------------------------------------------
# Full round-trip scenario
# ---------------------------------------------------------------------------


def test_full_webrtc_handshake_round():
    """A full WebRTC handshake round: offer → answer → ice (both directions).

    Each message in the round independently validates.
    """
    # Step 1: Consumer sends offer
    offer = {
        "type": "video_offer",
        "seq": 1,
        "ts": 1712345678000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "sdp": "v=0\no=- 100 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
            "qos_hint": "stable",
        },
    }
    assert _validate(offer) == []

    # Step 2: Robot sends answer
    answer = {
        "type": "video_answer",
        "seq": 100,
        "ts": 1712345679000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "sdp": "v=0\no=- 200 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n",
            "accepted": True,
        },
    }
    assert _validate(answer) == []

    # Step 3: Consumer sends ICE candidate
    consumer_ice = {
        "type": "video_ice",
        "seq": 2,
        "ts": 1712345680000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "candidate": "candidate:1 1 UDP 2122252543 192.168.1.100 49152 typ host",
            "sdp_mid": "0",
            "sdp_mline_index": 0,
        },
    }
    assert _validate(consumer_ice) == []

    # Step 4: Robot sends ICE candidate
    robot_ice = {
        "type": "video_ice",
        "seq": 101,
        "ts": 1712345680000000000,
        "body": {
            "stream_id": "camera_head",
            "subscriber_id": "web_dashboard_1",
            "candidate": "candidate:1 1 UDP 2122252543 10.0.0.1 49152 typ host",
            "sdp_mid": "0",
            "sdp_mline_index": 0,
        },
    }
    assert _validate(robot_ice) == []