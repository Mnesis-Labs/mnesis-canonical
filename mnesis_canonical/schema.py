"""Mnesis Canonical Schema — the field definitions (single source of truth).

This is the open standard ("具身数据的 USB-C") that every capture surface
(EgoWear phone / Mnesis-Iris, ProdigyHelper Quest / Mnesis-Eidolon,
TeleOP-Alohamini robot / Mnesis-Daedalus) and the Mnesis Ambrosia cloud platform
(mnesis-ambrosia) agree on. One frame = one JSON object = one JSONL line.

Authority: Mnesis-Labs/Parthenon `03 §3.2`. Keep this in lock-step with `SPEC.md` and
`canonical_frame.schema.json`. LeRobot-native; designed to stay compatible with
Isaac/GR00T data formats (see SPEC §Compatibility).
"""
from __future__ import annotations

from dataclasses import dataclass

# Capture-surface vocabularies (open set — extend deliberately, keep cross-repo in sync).
DEVICES = ("phone", "glasses", "quest", "pico", "robot", "sim")
MODALITIES = ("ego_human", "teleop", "robot_replay", "sim")

# Required JSON keys (dotted keys are intentional — LeRobot-style flat columns).
REQUIRED_KEYS = (
    "index",
    "episode_index",
    "task_index",
    "frame_index",
    "t_ns",
    "t_hw_ns",
    "timestamp",
    "head_pose_SE3",
    "observation.state",
    "observation.images.ego",
    "action",
    "source.device",
    "source.modality",
    "tracking_state",
)

# Fixed-length vector fields → expected length.
VECTOR_LENGTHS = {
    "head_pose_SE3": 7,      # [tx,ty,tz, qx,qy,qz,qw] metres + quaternion {x,y,z,w}
    "observation.state": 7,  # 7-DoF head/effector pose (mirrors head_pose_SE3)
    "action": 6,             # relative delta [tx,ty,tz, rx,ry,rz] (m, axis-angle rad)
}

INT_KEYS = ("index", "episode_index", "task_index", "frame_index", "t_ns", "t_hw_ns")
NULLABLE_KEYS = ("spatial_anchor_id",)  # optional but recommended


@dataclass(frozen=True)
class CanonicalFrame:
    """Typed convenience wrapper. The wire format is the dict / JSONL line."""

    index: int
    episode_index: int
    task_index: int
    frame_index: int
    t_ns: int
    t_hw_ns: int
    timestamp: str
    head_pose_se3: list[float]
    observation_state: list[float]
    observation_images_ego: str
    action: list[float]
    source_device: str
    source_modality: str
    tracking_state: str
    spatial_anchor_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "episode_index": self.episode_index,
            "task_index": self.task_index,
            "frame_index": self.frame_index,
            "t_ns": self.t_ns,
            "t_hw_ns": self.t_hw_ns,
            "timestamp": self.timestamp,
            "head_pose_SE3": list(self.head_pose_se3),
            "observation.state": list(self.observation_state),
            "observation.images.ego": self.observation_images_ego,
            "action": list(self.action),
            "spatial_anchor_id": self.spatial_anchor_id,
            "source.device": self.source_device,
            "source.modality": self.source_modality,
            "tracking_state": self.tracking_state,
        }

    @classmethod
    def from_dict(cls, d: dict) -> CanonicalFrame:
        return cls(
            index=d["index"],
            episode_index=d["episode_index"],
            task_index=d["task_index"],
            frame_index=d["frame_index"],
            t_ns=d["t_ns"],
            t_hw_ns=d["t_hw_ns"],
            timestamp=d["timestamp"],
            head_pose_se3=list(d["head_pose_SE3"]),
            observation_state=list(d["observation.state"]),
            observation_images_ego=d["observation.images.ego"],
            action=list(d["action"]),
            source_device=d["source.device"],
            source_modality=d["source.modality"],
            tracking_state=d["tracking_state"],
            spatial_anchor_id=d.get("spatial_anchor_id"),
        )
