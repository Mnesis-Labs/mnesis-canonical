# Mnesis Canonical Schema — Specification (v0.1)

> The open standard for **embodied spatial-action data** — one schema that every
> capture surface (phone / glasses / Quest / robot / sim) emits and the Mnesis
> Ambrosia platform ingests. LeRobot-native, dual-timestamp, spatial-anchored.
> Authority: Parthenon `03 §3.2`. Apache-2.0. **This file is the spec; the Python
> package is the reference implementation.**

## Why
Devices are replaceable "capture surfaces"; the **data format is the moat-adjacent
open standard** ("the USB-C of embodied data"). Anyone can adopt it for free → it
becomes the de-facto standard; Mnesis monetizes the proprietary core (high-fidelity
data, 4DGS physics, eval), not the schema.

## Unit
One **frame** = one JSON object = one line in an episode's `data.jsonl` sidecar.
An **episode** = `data.jsonl` (+ optional `video.mp4`) under one directory.

## Fields (all required unless noted)
| Key | Type | Meaning |
|---|---|---|
| `index` | int | Global monotonic frame index across episodes |
| `episode_index` | int | Episode id |
| `task_index` | int | Task within episode (0 = single-task) |
| `frame_index` | int | Frame index within episode (0-based, strictly increasing) |
| `t_ns` | int | Wall-clock nanoseconds (`System.nanoTime` base) |
| `t_hw_ns` | int | **Hardware** ns (ARCore `frame.timestamp`) — **join key** pose↔video |
| `timestamp` | str | ISO-8601 wall clock (e.g. `2026-06-26T00:00:00.000Z`) |
| `head_pose_SE3` | float[7] | `[tx,ty,tz, qx,qy,qz,qw]` metres + quaternion **{x,y,z,w}**, right-handed |
| `observation.state` | float[7] | 7-DoF state (mirrors `head_pose_SE3`) |
| `observation.images.ego` | str | File reference to the ego video frame (`""` allowed) |
| `action` | float[6] | Relative delta `[tx,ty,tz, rx,ry,rz]` (m, axis-angle rad) |
| `spatial_anchor_id` | str \| null | ARCore Anchor id (optional, recommended) |
| `source.device` | str | one of `phone, glasses, quest, pico, robot, sim` (open set) |
| `source.modality` | str | one of `ego_human, teleop, robot_replay, sim` (open set) |
| `tracking_state` | str | e.g. `TRACKING, PAUSED, STOPPED` |

### Conventions (iron rules)
- Quaternion order is **{x,y,z,w}** (scalar last). Right-handed.
- `action` is a **relative** delta, not absolute pose.
- `t_hw_ns` (not `t_ns`) is the join key between pose and video frames.
- Dotted keys (`observation.state`, `source.device`) are intentional flat columns (LeRobot style).

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

### Isaac Lab / GR00T field mapping (v0.1, working)
NVIDIA GR00T ingests **LeRobot-format** datasets, so the LeRobot-native columns
carry over 1:1; the remaining rows are either Canonical-only side channels or
open items to align with the platform authority before freezing. ✅ = settled,
ℹ️ = Canonical-only (drop/ignore on export), ⚠️ = **待对齐 Parthenon `03 §3.2`**.

| Canonical key | LeRobot feature | Isaac Lab / GR00T notion | Status |
|---|---|---|---|
| `observation.state` `float[7]` | `observation.state` | proprio / end-effector pose state | ✅ name + units (SI m, quat) 1:1 — see ⚠️ quaternion order below |
| `action` `float[6]` | `action` | action vector (Δpose) | ✅ relative delta, SI m + axis-angle rad — ⚠️ rotation representation (axis-angle vs Isaac euler/quat action) |
| `observation.images.ego` `str` | `observation.images.ego` | `observation.images.<cam>` | ✅ 1:1 file/key reference |
| `timestamp` | `timestamp` | dataset column | ✅ 1:1 (ISO-8601 string) |
| `index` / `episode_index` / `frame_index` / `task_index` | same | dataset columns | ✅ 1:1 |
| `head_pose_SE3` `float[7]` | (extra column) | root / sensor pose | ✅ SI m + quat — shares ⚠️ frame + quaternion items |
| `t_ns` / `t_hw_ns` `int` | (extra column) | — (GR00T keys on `timestamp`) | ℹ️ Canonical-only; `t_hw_ns` is the pose↔video join key — drop on GR00T export |
| `spatial_anchor_id` | (extra column) | — | ℹ️ Canonical-only spatial grounding |
| `source.device` / `source.modality` | (metadata) | embodiment tag / dataset metadata | ⚠️ map to GR00T embodiment tag — mapping table 待对齐 |
| `tracking_state` | (extra column) | — | ℹ️ Canonical-only QA flag |

**Open items (⚠️ 待对齐 Parthenon `03 §3.2` — do NOT freeze unilaterally):**
1. **Quaternion order.** Canonical is `{x,y,z,w}` scalar-last (ARCore); Isaac/USD convention is `{w,x,y,z}` scalar-first. Define the export adapter's reorder (and whether the wire format ever changes) with the platform authority.
2. **World frame / up-axis & handedness.** Both are right-handed, but ARCore is Y-up while Isaac Lab is typically Z-up. Pin the canonical world frame + the GR00T export transform.
3. **Action rotation representation.** Canonical `action` rotation is axis-angle (rad); confirm GR00T/Isaac action-space expectation before locking.
4. **Embodiment tagging.** Exact `source.device`/`source.modality` → GR00T embodiment-tag mapping.

Until these are resolved, conversion stays a **documented adapter concern**, not a wire-format change — the Canonical fields above are stable.

## Versioning
- Spec is versioned (`v0.1`). Additive fields = minor; breaking field change = major + migration note. `__version__` in the package mirrors this.

## Conformance
A producer is conformant if every line passes `mnesis_canonical.validate_frame` and
`frame_index` is strictly increasing per episode (`validate_frames`).
