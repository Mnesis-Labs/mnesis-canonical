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
    """Extract the Canonical Schema version (SPEC_VERSION) from the JSON Schema ``$id`` field.

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
#   ego_v1           — original v0.1 frame (fixed-length vectors, obs.images.ego required)
#   ego_multicam_v1  — ego_v1 with a NAMED camera SET instead of the single ego key
#   robot_v2         — robot-centric frame (variable-length state/action, open cameras, eef_pose)
PROFILES = ("ego_v1", "ego_multicam_v1", "robot_v2")
DEFAULT_PROFILE = "ego_v1"

# When profile is "robot_v2", these fields are variable-length (no fixed-size check).
ROBOT_V2_VARIABLE_VECTORS = ("observation.state", "action")

# --- Camera key set (C1, ego_multicam_v1) ------------------------------------
# Image references are flat dotted columns ``observation.images.<camera_name>``.
# ``ego_v1`` fixes the set to the single name ``ego``; ``ego_multicam_v1`` opens
# it to the NAMED set declared by the embodiment registry's
# ``capture.cameras[].name`` (a 5-camera ego rig cannot be squeezed into one key,
# and per-repo private key names would fork the standard — see SPEC §Profiles).
IMAGE_KEY_PREFIX = "observation.images."

# Camera names are registry identifiers, not free strings: lower snake_case, the
# same shape the registry files already use (``wide_l``, ``fisheye_c``, ``ego``).
CAMERA_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_]*$")


def camera_name(key: str) -> str | None:
    """Return the camera name of an ``observation.images.<name>`` key.

    Returns ``None`` for keys that are not image references at all.  The name may
    still be syntactically invalid (``""`` for a bare prefix) — validation of the
    name itself is :func:`mnesis_canonical.validate.validate_frame`'s job.
    """
    if not key.startswith(IMAGE_KEY_PREFIX):
        return None
    return key[len(IMAGE_KEY_PREFIX):]


def image_keys(frame: dict) -> list[str]:
    """Return the frame's ``observation.images.<camera_name>`` keys, in frame order.

    A camera that dropped the current frame has **no key at all** (absent means
    unknown — never an in-band sentinel), so this is also the per-frame answer to
    "which cameras actually delivered here".
    """
    return [k for k in frame if k.startswith(IMAGE_KEY_PREFIX)]


# Gripper observation channel (additive, optional).  Continuous gripper
# **closedness** as a first-class scalar in [0, 1] — direction identical to
# ``action.gripper`` and to the C3 xr_bridge wire field ``arms[].gripper``:
#   0.0 = fully open (完全张开)   1.0 = fully closed (完全闭合)
# Carried outside ``observation.state``/``action`` so consumers can read it
# without knowing a registry's vector layout.
#   observation.gripper        — single / main gripper (any profile, optional)
#   observation.gripper.left   — left  gripper (robot_v2 bimanual, optional)
#   observation.gripper.right  — right gripper (robot_v2 bimanual, optional)
# All optional and additive: frames without a gripper key validate unchanged.
GRIPPER_KEYS = (
    "observation.gripper",
    "observation.gripper.left",
    "observation.gripper.right",
)
GRIPPER_MIN = 0.0
GRIPPER_MAX = 1.0

# Field-level status values (mirror canonical_frame.schema.json `x-status` and
# SPEC.md §Versioning).  "stable" is the default / implicit value.
FIELD_STATUS = ("experimental", "stable", "deprecated")

# Experimental fields: frozen before promotion to `stable`.  These may be renamed
# or reshaped without counting as a breaking change.  (Authoritative `x-status`
# lives in canonical_frame.schema.json; this tuple keeps the pure-Python
# validator in lock-step.)
EXPERIMENTAL_KEYS = (
    "observation.hand.left",
    "observation.hand.right",
    "observation.hand.left.rot",
    "observation.hand.right.rot",
    "observation.hand.layout",
    "observation.hand.frame",
    "observation.hand.source",
)

# Deprecated fields: removed in a future major version.  Empty for now; the
# `--strict-stable` switch refuses both experimental and deprecated fields.
DEPRECATED_KEYS = ()

# Vendor extension namespace prefix pattern (x-<vendor>.<field>).
# Keys matching this prefix are reserved for vendor-specific extensions and
# are exempt from the unknown-key warning.  See SPEC.md §Conventions and
# extensions/registry.json.
VENDOR_EXTENSION_PREFIX = "x-"

# --- Hand keypoints (C11, additive, optional, status: experimental) ----------
# Skeleton-level hand data as a first-class observation.  The keypoint vectors
# are **variable-length**: their length is declared by ``observation.hand.layout``
# via the skeleton registry (``skeletons/<id>.json``), exactly the way
# ``observation.state``'s length is declared by the embodiment registry's
# ``joint_names``.  A fixed ``float[63]`` would freeze MediaPipe's 21-landmark
# topology into the open standard, which WebXR (25 joints) / OpenXR (26, with
# per-joint orientation) producers cannot emit without down-projecting away the
# orientation that skeleton retargeting exists to consume.
HAND_SIDES = ("left", "right")

# Joint POSITIONS, flattened xyz — length 3*K where K = layout joint_count.
HAND_KPTS_KEYS = ("observation.hand.left", "observation.hand.right")

# Joint ORIENTATIONS, flattened quaternions {x,y,z,w} — length 4*K.  Optional
# even when positions are present: MediaPipe-class sources have no orientation.
HAND_ROT_KEYS = ("observation.hand.left.rot", "observation.hand.right.rot")

HAND_LAYOUT_KEY = "observation.hand.layout"   # skeleton registry id
HAND_FRAME_KEY = "observation.hand.frame"     # reference frame, see HAND_FRAMES
HAND_SOURCE_KEY = "observation.hand.source"   # provenance label (open set)

# Reference frame of the keypoints.  This is the MACHINE-READABLE form of the
# "these are 2.5D, not true 3D" caveat: a consumer that needs world-localised
# hands filters on ``frame == "world"`` instead of maintaining a hard-coded
# allow-list of source strings.
#   world         — points are in the same world frame as head_pose_SE3.
#   head_anchored — metric and self-consistent WITHIN the hand, placed at the
#                   head/camera and rotated by the head pose; the hand's
#                   absolute position relative to the world is NOT recovered.
#                   (MediaPipe world landmarks + an AR head pose land here.)
#   hand_local    — origin is the hand itself (e.g. the wrist); no world
#                   placement claimed at all.
HAND_FRAMES = ("world", "head_anchored", "hand_local")

HAND_POSITION_DIMS = 3  # x, y, z per joint
HAND_ROTATION_DIMS = 4  # qx, qy, qz, qw per joint

# All hand keys, for consumers that want to strip or detect the whole block.
HAND_KEYS = (
    *HAND_KPTS_KEYS,
    *HAND_ROT_KEYS,
    HAND_LAYOUT_KEY,
    HAND_FRAME_KEY,
    HAND_SOURCE_KEY,
)

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

# Required JSON keys for the ego_multicam_v1 profile.  Identical to ego_v1 except
# that no single camera key is mandatory: the profile requires at least one
# ``observation.images.<camera_name>`` (checked in validate.py, which is where the
# registry cross-check lives).  ``observation.images.ego`` is not special here —
# it is simply "the camera named ego", so ego_v1 data is a subset with no migration.
_REQUIRED_KEYS_EGO_MULTICAM_V1 = tuple(
    k for k in _REQUIRED_KEYS_EGO_V1 if k != "observation.images.ego"
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
    if p == "ego_multicam_v1":
        return _REQUIRED_KEYS_EGO_MULTICAM_V1
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
    # Optional gripper *observation* channel (additive). Same normalized
    # closedness scale as action_gripper: 0.0 = fully open .. 1.0 = fully
    # closed. None = no gripper observation (distinct from 0.0).
    gripper: float | None = None
    gripper_left: float | None = None
    gripper_right: float | None = None
    # Optional hand keypoint block (C11, additive, experimental). Positions are
    # flattened xyz of length 3*K, orientations flattened {x,y,z,w} of length
    # 4*K, with K declared by ``hand_layout`` through the skeleton registry.
    # A hand that is not present is OMITTED ENTIRELY — never a zero vector, so
    # "no hand" and "hand at the origin" stay distinguishable.
    hand_left: list[float] | None = None
    hand_right: list[float] | None = None
    hand_left_rot: list[float] | None = None
    hand_right_rot: list[float] | None = None
    hand_layout: str | None = None
    hand_frame: str | None = None
    hand_source: str | None = None

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
        # ``observation.images.ego`` is required by ego_v1 (where "" is the legal
        # "no path yet" placeholder for its one camera).  Under a profile with an
        # open camera set it is merely "the camera named ego" — so a rig that has
        # no such camera must not be handed a blank one: that would fabricate the
        # very in-band sentinel the standard forbids.
        if not self.observation_images_ego and self.profile not in (None, "ego_v1"):
            del d["observation.images.ego"]
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
        if self.gripper is not None:
            d["observation.gripper"] = self.gripper
        if self.gripper_left is not None:
            d["observation.gripper.left"] = self.gripper_left
        if self.gripper_right is not None:
            d["observation.gripper.right"] = self.gripper_right
        if self.hand_left is not None:
            d["observation.hand.left"] = list(self.hand_left)
        if self.hand_right is not None:
            d["observation.hand.right"] = list(self.hand_right)
        if self.hand_left_rot is not None:
            d["observation.hand.left.rot"] = list(self.hand_left_rot)
        if self.hand_right_rot is not None:
            d["observation.hand.right.rot"] = list(self.hand_right_rot)
        if self.hand_layout is not None:
            d[HAND_LAYOUT_KEY] = self.hand_layout
        if self.hand_frame is not None:
            d[HAND_FRAME_KEY] = self.hand_frame
        if self.hand_source is not None:
            d[HAND_SOURCE_KEY] = self.hand_source
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
            gripper=d.get("observation.gripper"),
            gripper_left=d.get("observation.gripper.left"),
            gripper_right=d.get("observation.gripper.right"),
            hand_left=(
                list(d["observation.hand.left"])
                if "observation.hand.left" in d else None
            ),
            hand_right=(
                list(d["observation.hand.right"])
                if "observation.hand.right" in d else None
            ),
            hand_left_rot=(
                list(d["observation.hand.left.rot"])
                if "observation.hand.left.rot" in d else None
            ),
            hand_right_rot=(
                list(d["observation.hand.right.rot"])
                if "observation.hand.right.rot" in d else None
            ),
            hand_layout=d.get(HAND_LAYOUT_KEY),
            hand_frame=d.get(HAND_FRAME_KEY),
            hand_source=d.get(HAND_SOURCE_KEY),
        )
