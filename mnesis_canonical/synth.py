"""Deterministic synthetic episodes for demos / fixtures (pure stdlib, zero deps).

Generates canonical frames with believable head-pose trajectories for each
capture surface, so the trajectory plots and the end-to-end demo have something
worth looking at. Fully deterministic — no RNG, no wall-clock reads — so it is
reproducible and safe to reuse as a test fixture.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

_BASE_TIME = datetime(2026, 6, 26, 0, 0, 0, tzinfo=timezone.utc)


def _smoothstep(u: float) -> float:
    return u * u * (3.0 - 2.0 * u)


def _arc(u: float) -> tuple[float, float, float]:
    """Handheld ego scan: a horizontal arc swept at standing height."""
    theta = (u - 0.5) * math.pi * 0.8
    r = 0.5
    return (r * math.sin(theta), 1.4 + 0.05 * math.sin(u * 2 * math.pi), r * (1 - math.cos(theta)))


def _reach(u: float) -> tuple[float, float, float]:
    """Teleop grab: reach forward and down, curving out (ease-in/ease-out)."""
    s = _smoothstep(u)
    return (0.45 * math.sin(s * math.pi / 2), 1.1 - 0.30 * s, 0.5 * s)


def _replay(u: float) -> tuple[float, float, float]:
    """Robot replay: straighter path with a small tracking offset."""
    return (0.4 * u, 1.1 - 0.28 * u, 0.5 * u + 0.03 * math.sin(u * math.pi))


_SHAPES = {"arc": _arc, "reach": _reach, "replay": _replay}


def _yaw_quat(yaw: float) -> list[float]:
    """Rotation about the vertical axis (Y, ARCore up), canonical {x,y,z,w}."""
    return [0.0, math.sin(yaw / 2), 0.0, math.cos(yaw / 2)]


def synth_episode(
    *,
    episode_index: int,
    n_frames: int,
    device: str,
    modality: str,
    shape: str,
    fps: int = 30,
    start_index: int = 0,
    t_hw_base_ns: int = 1_000_000_000,
) -> list[dict]:
    """Build one deterministic canonical episode along the named ``shape``.

    ``action`` is the relative pose delta between consecutive frames (axis-angle
    rotation about the vertical), per SPEC. Frame 0's action is zero.
    """
    if n_frames < 2:
        raise ValueError("n_frames must be >= 2")
    fn = _SHAPES[shape]
    positions = [fn(i / (n_frames - 1)) for i in range(n_frames)]

    yaws = [0.0]
    for i in range(1, n_frames):
        dx = positions[i][0] - positions[i - 1][0]
        dz = positions[i][2] - positions[i - 1][2]
        yaws.append(math.atan2(dx, dz) if (dx or dz) else yaws[-1])

    frames: list[dict] = []
    for i in range(n_frames):
        px, py, pz = positions[i]
        pose = [px, py, pz, *_yaw_quat(yaws[i])]
        if i == 0:
            action = [0.0] * 6
        else:
            ppx, ppy, ppz = positions[i - 1]
            action = [px - ppx, py - ppy, pz - ppz, 0.0, yaws[i] - yaws[i - 1], 0.0]
        ms = round(i * 1000 / fps)
        dt = _BASE_TIME + timedelta(milliseconds=ms)
        ts = dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{dt.microsecond // 1000:03d}Z"
        frames.append(
            {
                "index": start_index + i,
                "episode_index": episode_index,
                "task_index": 0,
                "frame_index": i,
                "t_ns": 1_000_000 + ms * 1_000_000,
                "t_hw_ns": t_hw_base_ns + ms * 1_000_000,
                "timestamp": ts,
                "head_pose_SE3": [round(v, 6) for v in pose],
                "observation.state": [round(v, 6) for v in pose],
                "observation.images.ego": f"frames/{i:06d}.jpg",
                "action": [round(v, 6) for v in action],
                "spatial_anchor_id": (f"anchor-{device}-01" if device != "robot" else None),
                "source.device": device,
                "source.modality": modality,
                "tracking_state": "TRACKING",
            }
        )
    return frames


def demo_episodes() -> dict[str, list[dict]]:
    """The three canonical demo episodes (phone / quest / robot)."""
    return {
        "episode_phone": synth_episode(
            episode_index=0, n_frames=90, device="phone", modality="ego_human",
            shape="arc", fps=30, t_hw_base_ns=1_000_000_000,
        ),
        "episode_quest": synth_episode(
            episode_index=1, n_frames=60, device="quest", modality="teleop",
            shape="reach", fps=30, t_hw_base_ns=2_000_000_000,
        ),
        "episode_robot": synth_episode(
            episode_index=2, n_frames=60, device="robot", modality="robot_replay",
            shape="replay", fps=50, t_hw_base_ns=3_000_000_000,
        ),
    }
