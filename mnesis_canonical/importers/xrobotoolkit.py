"""XRoboToolkit ``.pkl`` → canonical episode importer (D-19a third input).

``mnesis-import xrobotoolkit teleop_log.pkl --out <dir>`` reads a Python pickle
from the XRoboToolkit ecosystem and emits a canonical ``robot_v2`` episode.

The pickle must contain a **list of message dicts** (or a dict with a ``"messages"``
key whose value is the list). Each message has:

    t_ns         int                 — wall-clock timestamp (nanoseconds)
    joint_state  [float, ...]        → observation.state
    joint_cmd    [float, ...] | None → action (fallback: hold last joint_state)
    ee_left      [7] | None          → observation.eef_pose.left (optional)
    ee_right     [7] | None          → observation.eef_pose.right (optional)
    images       {str: str} | None   → observation.images.<cam> (optional)
    gripper      float | None        → action.gripper (optional, in [0, 1])
    gripper_left  float | None       → observation.gripper.left (optional)
    gripper_right float | None       → observation.gripper.right (optional)
"""
from __future__ import annotations

import pickle
from pathlib import Path

from . import _common

SOURCE = "imported_xrobotoolkit_pickle"
SOURCE_FORMAT = "xrobotoolkit_pickle"
IMPORTER = "xrobotoolkit"

_IDENTITY_SE3 = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]

_FILL_STRATEGY = {
    "head_pose_SE3": "identity [0,0,0,0,0,0,1] (a robot embodiment has no head pose)",
    "action": "message.joint_cmd; fallback = hold last joint_state (quality downgrade)",
    "observation.eef_pose.{left,right}": "message.ee_left / ee_right when present",
    "observation.images.<cam>": "message.images path refs",
    "t_ns": "message t_ns (join key for pose<->video)",
    "source.device/modality": "robot / teleop",
    "action.gripper": "message.gripper when present",
    "observation.gripper.{left,right}": "message.gripper_left / gripper_right when present",
}


def _as_float_list(seq: object) -> list[float]:
    return [float(x) for x in seq]  # type: ignore[union-attr]


def _load_pickle(path: str | Path) -> list[dict]:
    """Load and normalize a XRoboToolkit pickle into a list of message dicts."""
    with open(path, "rb") as f:
        data = pickle.load(f)

    if isinstance(data, list):
        messages = data
    elif isinstance(data, dict):
        messages = data.get("messages") or data.get("frames") or []
        if not isinstance(messages, list):
            raise ValueError(
                "XRoboToolkit pickle: expected a list under 'messages' or 'frames' key, "
                f"got {type(messages).__name__}"
            )
    else:
        raise ValueError(
            "XRoboToolkit pickle: expected a list of messages or a dict with a "
            f"'messages' key, got {type(data).__name__}"
        )

    if not messages:
        raise ValueError("XRoboToolkit pickle has no messages")

    return messages


def convert(
    messages: list[dict], *, embodiment_id: str | None = None
) -> tuple[list[dict], dict]:
    """Convert XRoboToolkit pickle messages into canonical frames. Pure (no I/O)."""
    if not messages:
        raise ValueError("XRoboToolkit pickle has no messages")

    frames: list[dict] = []
    filled_fields: list[str] = []
    dropped_fields: list[str] = []
    action_holds = 0
    last_state: list[float] | None = None

    for i, m in enumerate(messages):
        t_ns = int(m["t_ns"])
        state = _as_float_list(m["joint_state"])

        if m.get("joint_cmd") is not None:
            action = _as_float_list(m["joint_cmd"])
        else:
            action = list(last_state) if last_state is not None else list(state)
            action_holds += 1
        last_state = state

        frame: dict = {
            "index": i,
            "episode_index": 0,
            "task_index": 0,
            "frame_index": i,
            "t_ns": t_ns,
            "t_hw_ns": t_ns,
            "timestamp": _common.iso_from_ns(t_ns),
            "head_pose_SE3": list(_IDENTITY_SE3),
            "observation.state": state,
            "action": action,
            "spatial_anchor_id": None,
            "source.device": "robot",
            "source.modality": "teleop",
            "tracking_state": "TRACKING",
            "profile": "robot_v2",
        }
        if embodiment_id is not None:
            frame["embodiment_id"] = embodiment_id

        images = m.get("images") or {}
        for cam, ref in images.items():
            frame[f"observation.images.{cam}"] = str(ref)
        if not images:
            filled_fields.append("observation.images.<cam> (no image in message)")

        if isinstance(m.get("ee_left"), (list, tuple)):
            frame["observation.eef_pose.left"] = _as_float_list(m["ee_left"])
        if isinstance(m.get("ee_right"), (list, tuple)):
            frame["observation.eef_pose.right"] = _as_float_list(m["ee_right"])

        # Optional gripper fields (v0.4+ additive, robot_v2).
        gripper = m.get("gripper")
        if gripper is not None:
            frame["action.gripper"] = float(gripper)
        gripper_left = m.get("gripper_left")
        if gripper_left is not None:
            frame["observation.gripper.left"] = float(gripper_left)
        gripper_right = m.get("gripper_right")
        if gripper_right is not None:
            frame["observation.gripper.right"] = float(gripper_right)

        frames.append(frame)

    reasons: list[str] = []
    if action_holds:
        filled_fields.append(f"action=hold_last ({action_holds} frame(s))")
        reasons.append(
            f"{action_holds} frame(s) missing joint_cmd → held last joint_state"
        )

    import_meta = _common.build_import_meta(
        importer=IMPORTER,
        source=SOURCE,
        source_format=SOURCE_FORMAT,
        embodiment_id=embodiment_id,
        frame_count=len(frames),
        fill_strategy=_FILL_STRATEGY,
        filled_fields=filled_fields,
        dropped_fields=dropped_fields,
        reasons=reasons,
    )
    return frames, import_meta


def import_pickle(
    pkl_path: str | Path, out_dir: str | Path, *, embodiment_id: str | None = None
) -> dict:
    """Read a XRoboToolkit pickle and write a canonical episode. Returns a summary."""
    messages = _load_pickle(pkl_path)
    frames, import_meta = convert(messages, embodiment_id=embodiment_id)
    return _common.write_episode(out_dir, frames, import_meta)