"""Regenerate the importer test fixtures (synthetic, self-made data only).

Run from the repo root:  python tests/fixtures/_generate.py

Produces:
  tests/fixtures/xrobotoolkit/teleop_log_synth.pkl

IMPORTANT: these contain NO third-party real data — every value is fabricated
here.
"""
from __future__ import annotations

import pickle
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent
# 2026-07-22T00:00:00Z in unix nanoseconds (synthetic capture start).
_START_UNIX_NS = 1_784_678_400_000_000_000


def make_xrobotoolkit_pickle() -> Path:
    """Generate a synthetic XRoboToolkit pickle fixture.

    Produces:  tests/fixtures/xrobotoolkit/teleop_log_synth.pkl
    """
    messages = []
    for i in range(4):
        msg = {
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
            "gripper": 0.5 + 0.1 * i,
            "gripper_left": 0.6 + 0.05 * i,
            "gripper_right": 0.4 + 0.05 * i,
        }
        messages.append(msg)

    out = FIXTURES / "xrobotoolkit"
    out.mkdir(parents=True, exist_ok=True)
    pkl_path = out / "teleop_log_synth.pkl"
    with open(pkl_path, "wb") as f:
        pickle.dump(messages, f)
    return pkl_path


if __name__ == "__main__":
    p = make_xrobotoolkit_pickle()
    print(f"wrote {p}")