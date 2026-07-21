"""Regenerate the importer test fixtures (synthetic, self-made data only).

Run from the repo root:  python tests/fixtures/_generate.py

Produces:
  tests/fixtures/xrobotoolkit/teleop_log_synth.pkl   (XRoboToolkit pickle)
  tests/fixtures/airbot/airdc_synth.mcap             (airbot MCAP, json messages)

IMPORTANT: these contain NO third-party real data — every value is fabricated
here. The tiny JPEG is a 1x1 pixel generated for the test.
"""
from __future__ import annotations

import base64
import json
import pickle
from pathlib import Path

# A genuine 1x1 white JPEG (fabricated here), to exercise the JPG camera-frame path.
_TINY_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof"
    "Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAAB"
    "AAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AfwD/2Q=="
)

FIXTURES = Path(__file__).resolve().parent
# 2026-07-22T00:00:00Z in unix nanoseconds (synthetic capture start).
_START_UNIX_NS = 1_784_678_400_000_000_000


def _joint(i: int, base: float) -> list[float]:
    # 7-DoF single AIRBOT Play arm (6 joints + gripper), small synthetic motion.
    return [round(base + 0.01 * i * k, 4) for k in range(1, 8)]


def make_xrobotoolkit_pickle() -> Path:
    frames = []
    for i in range(5):
        f = {
            "t": i / 50.0,  # 50 Hz teleop clock (seconds)
            "t_hw_ns": _START_UNIX_NS + i * 20_000_000,
            "joint_pos": _joint(i, 0.0),
            "joint_action": _joint(i, 0.05),
            "ee_pose": {"left": [0.5, 0.3, 0.2 + 0.01 * i, 0.0, 0.0, 0.0, 1.0]},
            "camera": {"ego": _TINY_JPEG},
            "xr_input": {"trigger": 0.0, "buttons": {"a": False, "b": False}},
        }
        # Frame 3 is missing the commanded action → exercises the hold-last fill.
        if i == 3:
            del f["joint_action"]
        frames.append(f)

    log = {
        "meta": {
            "hz": 50,
            "embodiment": "airbot_play",
            "task": "pick_place_synth",
            "episode_index": 0,
            "task_index": 0,
            "start_unix_ns": _START_UNIX_NS,
        },
        "frames": frames,
    }

    out = FIXTURES / "xrobotoolkit" / "teleop_log_synth.pkl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as fh:
        pickle.dump(log, fh, protocol=4)
    return out


def make_airbot_mcap() -> Path:
    from mnesis_canonical.importers import _mcap

    messages = []
    for i in range(4):
        payload = {
            "t_ns": _START_UNIX_NS + i * 20_000_000,
            # dual-arm (14-DoF) synthetic state/command.
            "joint_state": [round(0.01 * i * k, 4) for k in range(1, 15)],
            "joint_cmd": [round(0.05 + 0.01 * i * k, 4) for k in range(1, 15)],
            "ee_left": [0.5, 0.3, 0.2, 0.0, 0.0, 0.0, 1.0],
            "ee_right": [0.5, -0.3, 0.2, 0.0, 0.0, 0.0, 1.0],
            "images": {
                "wrist_left": f"frames/{i:06d}_left.jpg",
                "wrist_right": f"frames/{i:06d}_right.jpg",
            },
        }
        messages.append(
            {"log_time": payload["t_ns"], "data": json.dumps(payload).encode("utf-8")}
        )

    out = FIXTURES / "airbot" / "airdc_synth.mcap"
    return _mcap.write_messages(out, messages, topic="/airdc/frame", message_encoding="json")


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(FIXTURES.parent.parent))
    p1 = make_xrobotoolkit_pickle()
    p2 = make_airbot_mcap()
    print(f"wrote {p1}")
    print(f"wrote {p2}")
