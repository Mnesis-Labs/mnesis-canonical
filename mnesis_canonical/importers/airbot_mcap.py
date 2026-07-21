"""airbot_ie / AIRDC ``.mcap`` → canonical episode importer (D-19a second input).

``mnesis-import xrobotoolkit log.mcap --format airbot-mcap --out <dir>`` reads an
airbot MCAP log and emits a canonical ``robot_v2`` episode. This is the smoke
path for the v1.0 release: it exercises a genuine MCAP container end-to-end via
the pure-stdlib subset reader in :mod:`._mcap`.

The synthetic smoke fixture carries one JSON message per frame:

    {"t_ns": int,
     "joint_state": [float, ...],          → observation.state
     "joint_cmd":   [float, ...],          → action (fallback: hold joint_state)
     "ee_left":  [7] (optional),           → observation.eef_pose.left
     "ee_right": [7] (optional),           → observation.eef_pose.right
     "images": {cam: "path"} (optional)}   → observation.images.<cam>

Real airbot logs encode messages as FlatBuffers; decoding those is a documented
follow-up (see docs/RELEASE_CHECKLIST_v1.0.md) and does not block the smoke path.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import _common, _mcap

SOURCE = "imported_airbot_mcap"
SOURCE_FORMAT = "airbot_mcap"
IMPORTER = "xrobotoolkit"  # same CLI subcommand, second input format

_IDENTITY_SE3 = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]

_FILL_STRATEGY = {
    "head_pose_SE3": "identity [0,0,0,0,0,0,1] (a robot embodiment has no head pose)",
    "action": "message.joint_cmd; fallback = hold last joint_state (quality downgrade)",
    "observation.eef_pose.{left,right}": "message.ee_left / ee_right when present",
    "observation.images.<cam>": "message.images path refs; empty ego ref when absent",
    "t_ns": "MCAP message log_time (join key for pose<->video)",
    "source.device/modality": "robot / teleop",
}


def _as_float_list(seq: object) -> list[float]:
    return [float(x) for x in seq]  # type: ignore[union-attr]


def convert(
    messages: list[dict], *, embodiment_id: str | None = None
) -> tuple[list[dict], dict]:
    """Convert decoded airbot MCAP messages into canonical frames. Pure (no I/O)."""
    if not messages:
        raise ValueError("airbot MCAP has no messages")

    frames: list[dict] = []
    filled_fields: list[str] = []
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
            frame["observation.images.ego"] = ""
            filled_fields.append("observation.images.ego (no image in message)")

        if isinstance(m.get("ee_left"), (list, tuple)):
            frame["observation.eef_pose.left"] = _as_float_list(m["ee_left"])
        if isinstance(m.get("ee_right"), (list, tuple)):
            frame["observation.eef_pose.right"] = _as_float_list(m["ee_right"])

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
        dropped_fields=[],
        reasons=reasons,
    )
    return frames, import_meta


def import_mcap(
    mcap_path: str | Path, out_dir: str | Path, *, embodiment_id: str | None = None
) -> dict:
    """Read an airbot MCAP log and write a canonical episode. Returns a summary."""
    decoded: list[dict] = []
    for msg in _mcap.read_messages(mcap_path):
        if msg.channel.message_encoding not in ("json", ""):
            raise ValueError(
                f"unsupported MCAP message_encoding {msg.channel.message_encoding!r} "
                "(the smoke path reads json-encoded messages; FlatBuffers is a follow-up)"
            )
        decoded.append(json.loads(msg.data.decode("utf-8")))
    frames, import_meta = convert(decoded, embodiment_id=embodiment_id)
    return _common.write_episode(out_dir, frames, import_meta)
