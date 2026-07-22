# Mnesis Canonical Schema — Specification (v0.2)

> The open standard for **embodied spatial-action data** — one schema that every
> capture surface (phone / glasses / Quest / robot / sim) emits and the Mnesis
> Ambrosia platform ingests. LeRobot-native, dual-timestamp, spatial-anchored,
> profile-aware.
> Authority: Parthenon `03 §3.2`. Apache-2.0. **This file is the spec; the Python
> package is the reference implementation.**

## Why
Devices are replaceable "capture surfaces"; the **data format is the moat-adjacent
open standard** ("the USB-C of embodied data"). Anyone can adopt it for free → it
becomes the de-facto standard; Mnesis monetizes the proprietary core (high-fidelity
data, 4DGS physics, eval), not the schema.

v0.2 introduces the **profile** mechanism for additive schema evolution without
breaking existing data.

## Unit
One **frame** = one JSON object = one line in an episode's `data.jsonl` sidecar.
An **episode** = `data.jsonl` (+ optional `video.mp4`) under one directory.

## Profiles (v0.2+)

A frame may carry an optional `profile` field at the top level. When absent, it
defaults to `ego_v1` (identical to the v0.1 schema — full backward compatibility).

| Profile | Description | Key differences |
|---|---|---|
| `ego_v1` | Original v0.1 frame (default) | Fixed-length vectors, `observation.images.ego` required |
| `robot_v2` | Robot-centric frame | Variable-length `observation.state`/`action`, open camera keys, optional `eef_pose` |

### `ego_v1` profile
The original v0.1 frame. Fields are identical to the table below; no change in
wire format. All existing data and examples validate without modification.

### `robot_v2` profile
Designed for multi-DoF robot embodiments (e.g. dual-arm airbots):

- `observation.state` is **variable-length** `float[N]` — N and semantic order
  are defined by the `embodiment_id` registry's `joint_names` (arms concatenated
  left + right).
- `observation.images.<cam>` is an **open key set** — at least one camera key is
  required (`wrist_left`, `wrist_right`, `head`, `quest_cast`, etc.), no single
  camera is mandatory.
- `action` is **variable-length** — semantics (joint target or Δeef) declared by
  the registry.
- `observation.eef_pose.left` and `observation.eef_pose.right` (optional) —
  each `float[7]` `[tx,ty,tz, qx,qy,qz,qw]`.

## Fields (all required unless noted)
| Key | Type | Profile | Meaning |
|---|---|---|---|
| `index` | int | *all* | Global monotonic frame index across episodes |
| `episode_index` | int | *all* | Episode id |
| `task_index` | int | *all* | Task within episode (0 = single-task) |
| `frame_index` | int | *all* | Frame index within episode (0-based, strictly increasing) |
| `t_ns` | int | *all* | Wall-clock nanoseconds (`System.nanoTime` base) |
| `t_hw_ns` | int | *all* | **Hardware** ns (ARCore `frame.timestamp`) — **join key** pose↔video |
| `timestamp` | str | *all* | ISO-8601 wall clock (e.g. `2026-06-26T00:00:00.000Z`) |
| `head_pose_SE3` | float[7] | *all* | `[tx,ty,tz, qx,qy,qz,qw]` metres + quaternion **{x,y,z,w}**, right-handed |
| `observation.state` | float[7] or float[N] | *all* | 7-DoF state (`ego_v1`) or variable-length N (`robot_v2`, per registry `joint_names`) |
| `observation.images.ego` | str | `ego_v1` only | File reference to the ego video frame (`""` allowed) |
| `observation.images.<cam>` | str | `robot_v2` | Open camera key set — at least one required (`wrist_left`, `wrist_right`, `head`, etc.) |
| `action` | float[6] or float[N] | *all* | Relative delta `[tx,ty,tz, rx,ry,rz]` (`ego_v1`, 6) or variable-length N (`robot_v2`) |
| `observation.eef_pose.left` | float[7] | `robot_v2` optional | Left end-effector pose `[tx,ty,tz, qx,qy,qz,qw]` |
| `observation.eef_pose.right` | float[7] | `robot_v2` optional | Right end-effector pose `[tx,ty,tz, qx,qy,qz,qw]` |
| `action.gripper` | float | *all* optional | Gripper channel (v0.4+), **normalized** `[0.0, 1.0]` — `0.0` = fully open, `1.0` = fully closed. **Absence ≠ `0.0`** (absent = source provides no gripper info). Per-machine physical stroke lives in the embodiment registry, not per-frame |
| `spatial_anchor_id` | str \| null | *all* | ARCore Anchor id (optional, recommended) |
| `profile` | str | *all* optional | One of `ego_v1` (default) or `robot_v2` |
| `embodiment_id` | str \| null | *all* optional | Reference to embodiment registry entry (e.g. `"dual_airbot_v1"`) |
| `source.device` | str | *all* | one of `phone, glasses, quest, pico, robot, sim` (open set) |
| `source.modality` | str | *all* | one of `ego_human, teleop, robot_replay, sim` (open set) |
| `tracking_state` | str | *all* | e.g. `TRACKING, PAUSED, STOPPED` |

### Conventions (iron rules)
- Quaternion order is **{x,y,z,w}** (scalar last). Right-handed.
- `action` is a **relative** delta, not absolute pose.
- `t_hw_ns` (not `t_ns`) is the join key between pose and video frames.
- Dotted keys (`observation.state`, `source.device`) are intentional flat columns (LeRobot style).
- **Additive-only**: new fields do not break existing data. Profiles extend the
  schema without changing the wire format of previous profiles.

## Episode layout (on disk / upload)
```
episodes/ep_<n>/
  data.jsonl            # one CanonicalFrame per line  (required)
  video.mp4             # ego video, t_hw_ns-aligned    (optional)
  manifest.json         # {episodeIndex, frameCount, jsonlSizeBytes, videoPath, videoSizeBytes, durationMs}
```

## Compatibility (must stay true — `4c` DATA5)
- **LeRobot**: flat columns map 1:1 to LeRobot dataset features (`observation.state`, `action`, `timestamp`, `episode_index`, `frame_index`, `index`, `task_index`).
- **Isaac / GR00T**: keep field names + units (SI metres, rad) compatible so episodes can feed NVIDIA physical-AI pipelines without re-labeling. Diff/decisions tracked here before any field is frozen.
- **Profile backward compatibility**: v0.1 frames (no `profile` field) are treated as `ego_v1` and pass all validation unchanged.
- **`action.gripper` (v0.4+, additive-only)**: old data without this field is **valid** — consumers MUST treat a missing `action.gripper` as "no gripper info" and MUST NOT default it to `0.0` (open) or any other value. When present it is a normalized `float` in `[0.0, 1.0]`; out-of-range or non-numeric values are rejected. The `action` vector length is unchanged (`ego_v1` = 6, `robot_v2` = N); the gripper is an **independent optional field**, not a widened `action`.

### Isaac Lab / GR00T field mapping (v0.2, working)
NVIDIA GR00T ingests **LeRobot-format** datasets, so the LeRobot-native columns
carry over 1:1; the remaining rows are either Canonical-only side channels or
open items to align with the platform authority before freezing. ✅ = settled,
ℹ️ = Canonical-only (drop/ignore on export), ⚠️ = **待对齐 Parthenon `03 §3.2`**.

| Canonical key | LeRobot feature | Isaac Lab / GR00T notion | Status |
|---|---|---|---|
| `observation.state` `float[7]` or `float[N]` | `observation.state` | proprio / end-effector pose state | ✅ name + units (SI m, quat) 1:1 — see ⚠️ quaternion order below |
| `action` `float[6]` or `float[N]` | `action` | action vector (Δpose) | ✅ relative delta, SI m + axis-angle rad — ⚠️ rotation representation (axis-angle vs Isaac euler/quat action) |
| `observation.images.ego` / `<cam>` `str` | `observation.images.ego` | `observation.images.<cam>` | ✅ 1:1 file/key reference |
| `timestamp` | `timestamp` | dataset column | ✅ 1:1 (ISO-8601 string) |
| `index` / `episode_index` / `frame_index` / `task_index` | same | dataset columns | ✅ 1:1 |
| `head_pose_SE3` `float[7]` | (extra column) | root / sensor pose | ✅ SI m + quat — shares ⚠️ frame + quaternion items |
| `t_ns` / `t_hw_ns` `int` | (extra column) | — (GR00T keys on `timestamp`) | ℹ️ Canonical-only; `t_hw_ns` is the pose↔video join key — drop on GR00T export |
| `spatial_anchor_id` | (extra column) | — | ℹ️ Canonical-only spatial grounding |
| `profile` / `embodiment_id` | (metadata) | — | ℹ️ Canonical-only profile mechanism |
| `source.device` / `source.modality` | (metadata) | embodiment tag / dataset metadata | ⚠️ map to GR00T embodiment tag — mapping table 待对齐 |
| `tracking_state` | (extra column) | — | ℹ️ Canonical-only QA flag |

**Open items (⚠️ 待对齐 Parthenon `03 §3.2` — do NOT freeze unilaterally):**
1. **Quaternion order.** Canonical is `{x,y,z,w}` scalar-last (ARCore); Isaac/USD convention is `{w,x,y,z}` scalar-first. A reference export adapter exists — `mnesis_canonical.isaac.to_isaac` / `from_isaac` (reorders the pose-block quaternion, exact round-trip). It is **adapter-only; the wire format is unchanged.** Whether the canonical wire ever switches order is the only open call here.
2. **World frame / up-axis & handedness.** Both are right-handed, but ARCore is Y-up while Isaac Lab is typically Z-up. The adapter exposes an optional `world_transform` hook that **defaults to identity** (it does not guess a transform); pin the canonical world frame + the concrete GR00T export transform with the authority.
3. **Action rotation representation.** Canonical `action` rotation is axis-angle (rad); the adapter passes `action` through **verbatim** (do not consume the exported `action` as Isaac-native yet). Confirm GR00T/Isaac action-space expectation before locking.
4. **Embodiment tagging.** Exact `source.device`/`source.modality` → GR00T embodiment-tag mapping (not yet implemented in the adapter).

Until these are resolved, conversion stays a **documented adapter concern**, not a wire-format change — the Canonical fields above are stable.

## Versioning
- Spec is versioned (`v0.2`). Additive fields = minor; breaking field change = major + migration note. `__version__` in the package mirrors this.

## Conformance
A producer is conformant if every line passes `mnesis_canonical.validate_frame` and
`frame_index` is strictly increasing per episode (`validate_frames`).