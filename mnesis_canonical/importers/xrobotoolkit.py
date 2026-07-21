"""XRoboToolkit teleop-log → canonical episode importer (D-19a core).

``mnesis-import xrobotoolkit teleop_log_*.pkl --out <dir>`` turns a 50 Hz
XRoboToolkit teleop pickle (joint state + EE pose + JPG-compressed camera frames
+ XR input + synced timestamps) into a canonical ``robot_v2`` episode that passes
conformance and is ready to ``POST /api/episodes`` for a quality-score card.

Field mapping table (pickle key → canonical frame). Fills for missing fields are
explicit and recorded in ``import_meta.json`` (``fillStrategy`` / ``filledFields``):

    meta.hz / meta.start_unix_ns  → frame timing base (t_ns, timestamp)
    frame.t (seconds)             → t_ns  (relative → absolute via start_unix_ns)
    frame.t_hw_ns                 → t_hw_ns  (fallback: t_ns)
    frame.joint_pos               → observation.state   (variable-length float[N])
    frame.joint_action            → action              (fallback: hold last joint_pos)
    frame.ee_pose {left,right}|[7] → observation.eef_pose.{left,right}  (optional)
    frame.camera {cam: jpg|path}  → observation.images.<cam> (JPG bytes → frames/*.jpg)
    (none — robot has no head)    → head_pose_SE3 = identity
    meta.embodiment               → embodiment_id
    frame.xr_input                → dropped (XR controller input has no canonical field)

The importer only *reads* the canonical contract; provenance (``source =
imported_xrobotoolkit``) and the quality downgrade live in the sidecar.
"""
from __future__ import annotations

import pickle
from pathlib import Path

from . import _common

SOURCE = "imported_xrobotoolkit"
SOURCE_FORMAT = "xrobotoolkit_pickle"
IMPORTER = "xrobotoolkit"

# Robot frames have no head pose; canonical requires the 7-vector, so fill identity.
_IDENTITY_SE3 = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]

_FILL_STRATEGY = {
    "head_pose_SE3": "identity [0,0,0,0,0,0,1] (a robot embodiment has no head pose)",
    "action": (
        "commanded joint vector (frame.joint_action); "
        "fallback = hold last observed joint_pos (quality downgrade)"
    ),
    "observation.eef_pose.{left,right}": "frame.ee_pose when present; omitted otherwise",
    "observation.images.<cam>": "frame.camera JPG bytes written to frames/; '' when absent",
    "t_ns": "meta.start_unix_ns + frame.t*1e9 (relative teleop clock → absolute)",
    "source.device/modality": "robot / teleop (XRoboToolkit is a teleoperation surface)",
}


def _as_float_list(seq: object) -> list[float]:
    return [float(x) for x in seq]  # type: ignore[union-attr]


def convert(log: dict) -> tuple[list[dict], dict, dict[str, bytes]]:
    """Convert a loaded XRoboToolkit pickle dict into canonical frames.

    Returns ``(frames, import_meta, assets)`` where ``assets`` maps
    episode-relative paths to raw JPG bytes. Pure (no I/O).
    """
    meta = log.get("meta", {}) or {}
    raw_frames = log.get("frames", [])
    if not raw_frames:
        raise ValueError("XRoboToolkit log has no 'frames'")

    embodiment_id = meta.get("embodiment")
    episode_index = int(meta.get("episode_index", 0))
    task_index = int(meta.get("task_index", 0))
    start_unix_ns = int(meta.get("start_unix_ns", 0))

    frames: list[dict] = []
    assets: dict[str, bytes] = {}
    filled_fields: list[str] = []
    dropped_fields: list[str] = []
    action_holds = 0
    last_state: list[float] | None = None

    for i, rf in enumerate(raw_frames):
        t_ns = start_unix_ns + int(round(float(rf.get("t", 0.0)) * 1_000_000_000))
        t_hw_ns = int(rf.get("t_hw_ns", t_ns))

        state = _as_float_list(rf["joint_pos"])

        if "joint_action" in rf and rf["joint_action"] is not None:
            action = _as_float_list(rf["joint_action"])
        else:
            # Missing commanded action → hold last observed joint_pos (downgrade).
            action = list(last_state) if last_state is not None else list(state)
            action_holds += 1
        last_state = state

        frame: dict = {
            "index": i,
            "episode_index": episode_index,
            "task_index": task_index,
            "frame_index": i,
            "t_ns": t_ns,
            "t_hw_ns": t_hw_ns,
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

        # --- cameras: JPG bytes → frames/*.jpg, or pass through a path string ---
        cameras = rf.get("camera") or {}
        for cam, val in cameras.items():
            if isinstance(val, (bytes, bytearray)):
                rel = f"frames/{i:06d}_{cam}.jpg"
                assets[rel] = bytes(val)
                frame[f"observation.images.{cam}"] = rel
            else:
                frame[f"observation.images.{cam}"] = str(val)
        if not cameras:
            # robot_v2 requires at least one camera key; declare an empty ego ref.
            frame["observation.images.ego"] = ""
            filled_fields.append("observation.images.ego (no camera in source)")

        # --- end-effector pose (optional) ---
        ee = rf.get("ee_pose")
        if isinstance(ee, dict):
            if "left" in ee:
                frame["observation.eef_pose.left"] = _as_float_list(ee["left"])
            if "right" in ee:
                frame["observation.eef_pose.right"] = _as_float_list(ee["right"])
        elif isinstance(ee, (list, tuple)) and len(ee) == 7:
            frame["observation.eef_pose.left"] = _as_float_list(ee)

        if "xr_input" in rf and "xr_input" not in dropped_fields:
            dropped_fields.append("xr_input")

        frames.append(frame)

    reasons: list[str] = []
    if action_holds:
        filled_fields.append(f"action=hold_last ({action_holds} frame(s))")
        reasons.append(
            f"{action_holds} frame(s) missing commanded action → held last joint_pos"
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
    return frames, import_meta, assets


def import_pickle(pkl_path: str | Path, out_dir: str | Path) -> dict:
    """Load an XRoboToolkit pickle and write a canonical episode. Returns a summary."""
    with open(pkl_path, "rb") as f:
        log = pickle.load(f)
    if not isinstance(log, dict):
        raise ValueError(
            f"expected a dict at the top level of the pickle, got {type(log).__name__}"
        )
    frames, import_meta, assets = convert(log)
    return _common.write_episode(out_dir, frames, import_meta, assets)
