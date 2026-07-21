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

import json
import re
from dataclasses import dataclass
from pathlib import Path

# Path to the bundled JSON Schema (single source of truth for $id/version).
_SCHEMA_PATH = Path(__file__).resolve().parent / "canonical_frame.schema.json"
_VERSION_RE = re.compile(r"/(v[\w.]+)\.json$")


def get_schema_version() -> str:
    """Extract the Canonical Schema version from the JSON Schema ``$id`` field.

    Returns a string like ``"v0.2"``, or ``"unknown"`` if parsing fails.
    """
    try:
        with open(_SCHEMA_PATH, encoding="utf-8") as f:
            schema = json.load(f)
        sid = schema.get("$id", "")
        m = _VERSION_RE.search(sid)
        if m:
            return m.group(1)
    except (OSError, json.JSONDecodeError):
        pass
    return "unknown"

# Capture-surface vocabularies (open set — extend deliberately, keep cross-repo in sync).
DEVICES = ("phone", "glasses", "quest", "pico", "robot", "sim")
MODALITIES = ("ego_human", "teleop", "robot_replay", "sim")

# Profile names (v0.2+).
#   ego_v1   — original v0.1 frame (fixed-length vectors, obs.images.ego required)
#   robot_v2 — robot-centric frame (variable-length state/action, open cameras, eef_pose)
PROFILES = ("ego_v1", "robot_v2")
DEFAULT_PROFILE = "ego_v1"

# When profile is "robot_v2", these fields are variable-length (no fixed-size check).
ROBOT_V2_VARIABLE_VECTORS = ("observation.state", "action")

# Required JSON keys for the default ego_v1 profile (dotted keys — LeRobot-style flat columns).
_REQUIRED_KEYS_EGO_V1 = (
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

# Required JSON keys for the robot_v2 profile (no fixed camera key, variable vectors).
_REQUIRED_KEYS_ROBOT_V2 = (
    "index",
    "episode_index",
    "task_index",
    "frame_index",
    "t_ns",
    "t_hw_ns",
    "timestamp",
    "head_pose_SE3",
    "observation.state",
    "action",
    "source.device",
    "source.modality",
    "tracking_state",
)

# For v0.1 backwards-compat: the base set of required keys is the ego_v1 set.
REQUIRED_KEYS = _REQUIRED_KEYS_EGO_V1


def required_keys_for_profile(profile: str | None) -> tuple[str, ...]:
    """Return the required key set for the given profile name."""
    p = profile or DEFAULT_PROFILE
    if p == "robot_v2":
        return _REQUIRED_KEYS_ROBOT_V2
    return _REQUIRED_KEYS_EGO_V1


# Fixed-length vector fields → expected length (applies to ego_v1 profile).
VECTOR_LENGTHS = {
    "head_pose_SE3": 7,      # [tx,ty,tz, qx,qy,qz,qw] metres + quaternion {x,y,z,w}
    "observation.state": 7,  # 7-DoF head/effector pose (mirrors head_pose_SE3)
    "action": 6,             # relative delta [tx,ty,tz, rx,ry,rz] (m, axis-angle rad)
}

INT_KEYS = ("index", "episode_index", "task_index", "frame_index", "t_ns", "t_hw_ns")
NULLABLE_KEYS = ("spatial_anchor_id",)  # optional but recommended

# Events.jsonl type vocabulary (v0.2+).
EVENT_TYPES = (
    "plan_preview",
    "execute_confirm",
    "estop",
    "episode_mark",
    "anchor_set",
)

# Spans annotation vocabulary (v0.3+).
# Hand enum values for annotations/spans.jsonl.
ANNOTATION_HANDS = ("left", "right", "both", "none")

# Visibility enum values for spans.
ANNOTATION_VISIBILITIES = ("visible", "occluded", "out_of_frame")

# Source enum values for spans.
# ``iris_heuristic`` =端上启发式粗分段 (Mnesis-Iris, spans.draft.jsonl); additive.
ANNOTATION_SOURCES = ("argus_v0", "human", "external", "iris_heuristic")

# Manipulation action taxonomy (v0.3+).  Every span.action MUST be one of these.
# These mirror the verbs in taxonomies/manipulation_v1.json.
MANIPULATION_ACTIONS = (
    "reaching",
    "grasping_pinching",
    "lifting",
    "holding",
    "placing_inserting",
    "pushing_pulling",
    "rotating",
    "opening_closing",
    "releasing",
    "pressing_sliding",
    "pouring",
    "bimanual_coordination",
    "tool_use",
    "idle",
)


@dataclass(frozen=True)
class CanonicalFrame:
    """Typed convenience wrapper. The wire format is the dict / JSONL line.

    ``profile`` (optional, defaults to ``"ego_v1"``) and ``embodiment_id``
    (optional) are v0.2+ fields.  When ``profile="robot_v2"``, the frame
    uses variable-length vectors and open camera-key semantics.
    """

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
    profile: str | None = None
    embodiment_id: str | None = None
    observation_images: dict[str, str] | None = None
    eef_pose_left: list[float] | None = None
    eef_pose_right: list[float] | None = None
    # Optional gripper channel (v0.4+, additive). Normalized 0.0 (fully open)
    # .. 1.0 (fully closed). None = source does not provide gripper info
    # (semantically distinct from 0.0). Physical stroke lives in the embodiment
    # registry, not per-frame.
    action_gripper: float | None = None

    def to_dict(self) -> dict:
        d: dict = {
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
        if self.profile is not None:
            d["profile"] = self.profile
        if self.embodiment_id is not None:
            d["embodiment_id"] = self.embodiment_id
        if self.observation_images is not None:
            for cam_key, ref in self.observation_images.items():
                d[f"observation.images.{cam_key}"] = ref
        if self.eef_pose_left is not None:
            d["observation.eef_pose.left"] = list(self.eef_pose_left)
        if self.eef_pose_right is not None:
            d["observation.eef_pose.right"] = list(self.eef_pose_right)
        if self.action_gripper is not None:
            d["action.gripper"] = self.action_gripper
        return d

    @classmethod
    def from_dict(cls, d: dict) -> CanonicalFrame:
        # Extract extra camera keys (observation.images.<cam>)
        obs_images: dict[str, str] = {}
        for key, val in d.items():
            if key.startswith("observation.images."):
                cam = key[len("observation.images."):]
                if cam:  # skip empty
                    obs_images[cam] = val

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
            observation_images_ego=d.get("observation.images.ego", ""),
            action=list(d["action"]),
            source_device=d["source.device"],
            source_modality=d["source.modality"],
            tracking_state=d["tracking_state"],
            spatial_anchor_id=d.get("spatial_anchor_id"),
            profile=d.get("profile"),
            embodiment_id=d.get("embodiment_id"),
            observation_images=(
                obs_images if len(obs_images) > 1 or "ego" not in obs_images else None
            ),
            eef_pose_left=(
                list(d["observation.eef_pose.left"])
                if "observation.eef_pose.left" in d else None
            ),
            eef_pose_right=(
                list(d["observation.eef_pose.right"])
                if "observation.eef_pose.right" in d else None
            ),
            action_gripper=d.get("action.gripper"),
        )
