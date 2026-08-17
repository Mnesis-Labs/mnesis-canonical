# Mnesis Canonical Schema — Specification (SPEC_VERSION v0.2)

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
- `observation.gripper` (optional, any profile; `.left` / `.right` for bimanual
  `robot_v2`) — gripper **closedness** as a continuous scalar in `[0.0, 1.0]`,
  **`0.0` = fully open, `1.0` = fully closed**. Carried as a first-class field so
  consumers read it without knowing a registry's vector layout. The direction is
  **identical to `action.gripper`** and to the C3 xr_bridge wire field
  `arms[].gripper` (see `contracts/XR_ROBOT_CONTRACT.md`): a teleop frame records
  the commanded gripper via `action.gripper` and the observed gripper via
  `observation.gripper` on the **same** `[0,1]` closedness scale. All gripper
  keys are **optional and additive** — frames without them validate unchanged.

### Gripper channel (C8, additive)
The gripper is a **continuous scalar in `[0.0, 1.0]`** (`0.0` = fully open, `1.0` = fully
closed) carried as an optional first-class field — not folded into
`observation.state`/`action` — so consumers can read it without knowing a
registry's vector layout:

- `observation.gripper` — single / main gripper (any profile).
- `observation.gripper.left` / `observation.gripper.right` — per-side grippers
  for bimanual `robot_v2` embodiments (mirrors `observation.eef_pose.{left,right}`).

Semantics align 1:1 with the C3 xr_bridge wire field `arms[].gripper` (`夹爪闭合
程度 [0,1]`, see `contracts/XR_ROBOT_CONTRACT.md`): a teleop frame records the
commanded/executed gripper closedness on the same `[0,1]` closedness scale. All gripper keys
are **optional and additive** — frames without them validate unchanged.

## Fields (all required unless noted)

The **Status** column records each field's [field-level status](#versioning)
(`stable` unless marked `[experimental]` / `[deprecated]`); the authoritative
value lives in `canonical_frame.schema.json`'s per-property `x-status`.

| Key | Type | Profile | Meaning | Status |
|---|---|---|---|---|
| `index` | int | *all* | Global monotonic frame index across episodes | `stable` |
| `episode_index` | int | *all* | Episode id | `stable` |
| `task_index` | int | *all* | Task within episode (0 = single-task) | `stable` |
| `frame_index` | int | *all* | Frame index within episode (0-based, strictly increasing) | `stable` |
| `t_ns` | int | *all* | Wall-clock nanoseconds (`System.nanoTime` base) | `stable` |
| `t_hw_ns` | int | *all* | **Hardware** ns (ARCore `frame.timestamp`) — **join key** pose↔video | `stable` |
| `timestamp` | str | *all* | ISO-8601 wall clock (e.g. `2026-06-26T00:00:00.000Z`) | `stable` |
| `head_pose_SE3` | float[7] | *all* | `[tx,ty,tz, qx,qy,qz,qw]` metres + quaternion **{x,y,z,w}**, right-handed | `stable` |
| `observation.state` | float[7] or float[N] | *all* | 7-DoF state (`ego_v1`) or variable-length N (`robot_v2`, per registry `joint_names`) | `stable` |
| `observation.images.ego` | str | `ego_v1` only | File reference to the ego video frame (`""` allowed) | `stable` |
| `observation.images.<cam>` | str | `robot_v2` | Open camera key set — at least one required (`wrist_left`, `wrist_right`, `head`, etc.) | `stable` |
| `action` | float[6] or float[N] | *all* | Relative delta `[tx,ty,tz, rx,ry,rz]` (`ego_v1`, 6) or variable-length N (`robot_v2`) | `stable` |
| `observation.eef_pose.left` | float[7] | `robot_v2` optional | Left end-effector pose `[tx,ty,tz, qx,qy,qz,qw]` | `stable` |
| `observation.eef_pose.right` | float[7] | `robot_v2` optional | Right end-effector pose `[tx,ty,tz, qx,qy,qz,qw]` | `stable` |
| `action.gripper` | float | *all* optional | Gripper channel (v0.4+), **normalized** `[0.0, 1.0]` — `0.0` = fully open, `1.0` = fully closed. **Absence ≠ `0.0`** (absent = source provides no gripper info). Per-machine physical stroke lives in the embodiment registry, not per-frame | `stable` |
| `observation.gripper` | float | *all* optional | Gripper **closedness** observation, **normalized** `[0.0, 1.0]` — `0.0` = fully open, `1.0` = fully closed (direction identical to `action.gripper`). Single / main gripper | `stable` |
| `observation.gripper.left` | float | `robot_v2` optional | Left gripper closedness `[0.0, 1.0]` (`0.0` = fully open, `1.0` = fully closed); bimanual | `stable` |
| `observation.gripper.right` | float | `robot_v2` optional | Right gripper closedness `[0.0, 1.0]` (`0.0` = fully open, `1.0` = fully closed); bimanual | `stable` |
| `observation.hand.left` | float[3K] | *all* optional | **[experimental]** Left-hand joint **positions**, flattened `[x0,y0,z0, x1,y1,z1, …]` in metres. `K` = `joint_count` of `observation.hand.layout`. Absent hand = key **omitted entirely** | `experimental` |
| `observation.hand.right` | float[3K] | *all* optional | **[experimental]** Right-hand joint positions; same rules | `experimental` |
| `observation.hand.left.rot` | float[4K] | *all* optional | **[experimental]** Left-hand joint **orientations**, flattened quaternions **{x,y,z,w}**. Only from sources that natively provide it | `experimental` |
| `observation.hand.right.rot` | float[4K] | *all* optional | **[experimental]** Right-hand joint orientations; same rules | `experimental` |
| `observation.hand.layout` | str | *all* optional | **[experimental]** Skeleton layout id (`skeletons/<id>.json`), e.g. `mediapipe_hand_21`. **Required when any hand keypoint vector is present** | `experimental` |
| `observation.hand.frame` | str | *all* optional | **[experimental]** One of `world`, `head_anchored`, `hand_local` — the reference frame of the keypoints. **Required when any hand keypoint vector is present** | `experimental` |
| `observation.hand.source` | str | *all* optional | **[experimental]** Provenance label (open set), e.g. `mediapipe_world+arcore_pose`. Provenance **only** — geometry lives in `observation.hand.frame` | `experimental` |
| `spatial_anchor_id` | str \| null | *all* | ARCore Anchor id (optional, recommended) | `stable` |
| `spatial_anchor_pose_SE3` | list \| null | *all* optional | The **anchor's own** world-frame pose `[tx,ty,tz, qx,qy,qz,qw]`. This — not `head_pose_SE3` — is what identifies an anchor; supply it when the capture surface can localise the anchor, and conflicting definitions of the same `spatial_anchor_id` are checked against it. Omit when unavailable: the id still travels, only the consistency check is skipped. | `stable` |
| `profile` | str | *all* optional | One of `ego_v1` (default) or `robot_v2` | `stable` |
| `embodiment_id` | str \| null | *all* optional | Reference to embodiment registry entry (e.g. `"dual_airbot_v1"`) | `stable` |
| `source.device` | str | *all* | one of `phone, glasses, quest, pico, robot, sim` (open set) | `stable` |
| `source.modality` | str | *all* | one of `ego_human, teleop, robot_replay, sim` (open set) | `stable` |
| `tracking_state` | str | *all* | e.g. `TRACKING, PAUSED, STOPPED` | `stable` |

> **Note:** this table supersedes the duplicate `observation.gripper[.left|.right]`
> "C8" rows that previously appeared immediately above it (stale copy, `[deprecated]`).

### Conventions (iron rules)
- Quaternion order is **{x,y,z,w}** (scalar last). Right-handed.
- `action` is a **relative** delta, not absolute pose.
- `t_hw_ns` (not `t_ns`) is the join key between pose and video frames.
- Dotted keys (`observation.state`, `source.device`) are intentional flat columns (LeRobot style).
- **Additive-only**: new fields do not break existing data. Profiles extend the
  schema without changing the wire format of previous profiles.
- **Absent means unknown (iron rule).** Never encode "unknown / not applicable" as an
  in-band sentinel — `0`, a zero vector, `-1`, `NaN`, `""`, a presence flag bit,
  or any other out-of-domain value. If a value is unknown or the source does not
  provide it, **omit the key entirely**. Consumers MUST NOT substitute a default for
  a missing optional field. This rule is the common principle behind two prior
  rulings (see `CONTRACTS.md` C1):
- **Vendor extension namespace**: keys starting with `x-<vendor>.` (e.g.
  `x-iris.hand_left_kpts3d`) are **reserved for vendor-specific extensions**.
  The schema explicitly acknowledges this prefix via `patternProperties` in the
  JSON Schema, and the validator emits a **warning** (not an error) for any
  unknown key that does **not** match this reserved prefix. Vendors register
  their extensions in `extensions/registry.json` (see `CONTRACTS.md`). The
  additive commitment is preserved: unknown keys never break validation, but
  non-reserved unknown keys become visible.
  - 2026-07-21 · `action.gripper` absent ≠ `0.0` (source provides no gripper info);
  - 2026-07-27 · `spatial_anchor_pose_SE3` absent ⇒ skip the anchor consistency
    check, **do not fall back to `head_pose_SE3`**.
  It also governs an untracked hand omitting `observation.hand.<side>` rather than
  sending zeros, and rules out "hand-pose-as-sentinel" schemes
  (presence-flag + zero-padding) that would encode absence inside the value space.

## Hand keypoints (C11, additive, `experimental`)

Skeleton-level hand data as a first-class observation — the field that Eidolon's
WebXR hand channel, Iris's on-device estimator, and Argus's offline refinement
all write, instead of each capture surface inventing its own.

### Variable length + a declared layout
The keypoint vectors are **variable-length**. Their length is declared by
`observation.hand.layout`, resolved against the **skeleton registry**
(`skeletons/<id>.json`) — exactly the mechanism by which `embodiment_id`'s
`joint_names` declares the length of `observation.state`:

```
len(observation.hand.<side>)      == 3 * layout.joint_count
len(observation.hand.<side>.rot)  == 4 * layout.joint_count
```

A fixed `float[63]` would have frozen MediaPipe's 21-landmark topology into the
open standard. WebXR Hand Input carries 25 joints and OpenXR 26, both with
per-joint orientation, and skeleton retargeting consumes exactly that
orientation — so a fixed length would have forced every XR producer to either
down-project (losing orientation) or fork the field.

Registered layouts:

| id | joints | orientation | status |
|---|---|---|---|
| `mediapipe_hand_21` | 21 | no | `stable` |
| `webxr_hand_25` | 25 | yes | `experimental` |
| `openxr_hand_26` | 26 | yes | `experimental` |

Adding a layout is a registry PR, not a schema change.

### Reference frame — the 2.5D caveat, made machine-readable
`observation.hand.frame` is **required whenever keypoints are present**:

| value | meaning |
|---|---|
| `world` | Points are in the same world frame as `head_pose_SE3`. |
| `head_anchored` | Metric and self-consistent **within the hand**, placed at the head/camera and rotated by the head pose — but the hand's **absolute position relative to the world is not recovered**. Monocular world-landmark estimators land here. |
| `hand_local` | Origin is the hand itself; no world placement is claimed. |

A consumer that needs world-localised hands filters on `frame == "world"`.
It must **not** infer this from `observation.hand.source`: that is an open string
set, and putting geometric semantics in a provenance label would force every
consumer to maintain a hard-coded allow-list of source strings.

### Presence
An untracked hand **omits its key entirely** — never a zero vector, never `null`
(see the iron rule above). `observation.hand.<side>.rot` may only appear
alongside its own side's position vector.

### Not on the wire: the concatenated LeRobot vector
A single per-frame `[leftPresent, rightPresent, left…, right…]` observation
vector is a **derived projection**: it is recomputable from the fields above, and
its zero-padding for an absent hand contradicts the presence rule. Derived
shapes belong to the exporter, not the wire format — otherwise every downstream
trainer's convenience layout ends up as a redundant column with its own
"which one wins" consistency check.

### Migrating pre-standard data
Data produced before this section (Mnesis-Iris, from D-13) used
`hand_left_kpts3d` / `hand_right_kpts3d` / `hand_kpts_source` / `hand_pose`.
The validator does **not** accept those names — aliases in an open standard never
die. Rewrite once instead:

```bash
python -m mnesis_canonical migrate episodes/ep_0/data.jsonl --out episodes/ep_0/data.jsonl
```

or `mnesis_canonical.migrate_hand_v0_frames(frames)` in-process. The migration
renames the three carried fields, drops the derived `hand_pose`, and declares
`layout = mediapipe_hand_21` + `frame = head_anchored`.

## Dual-endpoint semantic perception (C12, PS0)

The robot end (Mnesis-Daedalus) and the headset end (Mnesis-Eidolon) look at the
same room and produce **the same kind of thing**: "there is a `cup` at this pose
in the map, and I am 0.87 sure". This section defines that thing once, here,
before either end implements it — the C1 video-signalling precedent: canonical
defines, both ends consume read-only. Two independently-defined schemas would
mean the fuser opens with an adapter layer and `class_id` drifts on day one.

This repo defines the contract only. Fusion is Daedalus (ADR-004); headset-side
consumption is Eidolon. Reference implementation of the validators:
`mnesis_canonical.semantic`; JSON Schema for non-Python consumers:
`mnesis_canonical/semantic.schema.json`; golden samples: `examples/semantic/`.

### `ObservationLabel` — what both ends emit

| Key | Type | Req | Meaning |
|---|---|---|---|
| `label_id` | str | ✅ | Stable id for this object **across frames** (UUIDv4 recommended). Re-observing the same object reuses it — that is what makes tracking possible |
| `class_id` | str | ✅ | Object class, **from `taxonomies/object_class_v1.json`** — see below |
| `confidence` | float | ✅ | `[0, 1]`. Required: an input without a stated confidence cannot be fused. Human adjudication uses `1.0` |
| `source` | str | ✅ | `robot` \| `headset` \| `human` |
| `sensor` | str | optional | Producer-local sensor id (`cam_overhead`). **Provenance only** — geometry is `frame_id`, exactly as `observation.hand.source` carries no geometry |
| `frame_id` | str | ✅ | Must be `map` — the **shared** frame. A sensor- or headset-local pose is rejected, not silently mis-fused |
| `pose` | obj | ✅ | `{"t": [x,y,z], "q": [x,y,z,w]}` — metres + **unit** quaternion, scalar last, right-handed (same convention as `head_pose_SE3`) |
| `extent` | float[3] | optional | 3D bbox size `[dx,dy,dz]` in metres, positive. **Omit when unknown** — never null, never zeros (§Conventions) |
| `observed_at_ns` | int | ✅ | When the observation was made, **Unix nanoseconds** — distinct from the envelope `ts` (when the message was sent) |

`source` carries **`headset` and `human` from day one**, although headset-side
recognition (PS4) and human adjudication are backlog. Widening an enum later is a
contract change every consumer has to revisit; the two values cost nothing now.

**Nanoseconds, not float seconds.** The PS0 draft used `observed_at` in
fractional seconds. The standard already has exactly one time unit — `t_ns`,
`t_hw_ns`, `events.jsonl` `t_ns`, and the C3 envelope `ts` are all integer
nanoseconds — and a second unit inside one wire format is a conversion bug
waiting on a boundary. Named `observed_at_ns` so the unit is in the field name.

### `class_id` — the value domain is registered, not invented

`taxonomies/object_class_v1.json` is the **only** source of `class_id`, resolved
through the taxonomy registry (`mnesis_canonical.taxonomy_registry`, the same
mechanism as `skeletons/` for `observation.hand.layout` and `embodiments/` for
`observation.state`). A class the two ends need but the file lacks is a **PR
against that file** — never a locally invented string, because the fusion
contract exists precisely so that `cup` from the headset and `cup` from the robot
are the same term. `unknown` is a real observation with an undetermined class,
**not** a hole for a missing taxonomy entry.

### `scene_graph` — the fused product (robot end authoritative)

```jsonc
{
  "map_id": "lab_bench_a",
  "revision": 42,                  // monotonic per map_id; consumers redraw off it
  "updated_at_ns": 1785196801480000000,
  "labels": [{
    /* ...ObservationLabel... */
    "state":     "confirmed",      // confirmed | unconfirmed | disputed | stale
    "witnesses": ["robot", "headset"],
    "dispute":   { "robot": "cup", "headset": "bottle" }   // iff state == disputed
  }]
}
```

- `state`: `confirmed` (corroborated) · `unconfirmed` (one witness, uncontradicted)
  · `disputed` (witnesses disagree on the class) · `stale` (not re-observed
  recently, still believed to exist). **A `stale` label is not dropped**: "I no
  longer see it" and "it is gone" are different claims, and only the producer can
  tell them apart. Consumers render it degraded.
- `witnesses` ⊆ `{robot, headset, human}`, unique, and MUST contain the label's
  own `source`.
- `dispute` is present **exactly when** `state == "disputed"`: it maps each
  disagreeing witness to what it called the object, its keys are a subset of
  `witnesses`, its values come from the same taxonomy, and they must actually
  differ. Without it the graph records *that* there was a disagreement but not
  what it was — which is the one thing a human adjudication needs to resolve it.
- `label_id` is unique within a graph; an empty `labels` array is valid (an empty
  map is a real state).

### The three 8442 messages (envelope v1)

Envelope v1 is the **C3 public header verbatim** — `{type, seq, ts, body}`,
`seq` uint32, `ts` int64 Unix ns — because these ride the same 8442 socket a
bridge already demultiplexes for teleop.

| Type | Direction | Rate | `body` |
|---|---|---|---|
| `semantic_label` | up (headset → bridge) | event-driven, ≤ 5 Hz | `{map_id, labels[≥1]}`, each label `source ∈ {headset, human}` |
| `scene_graph` | down (bridge → headset) | **1–5 Hz, change-driven** | the `scene_graph` object above |
| `colocalization` | bidirectional | **≤ 1 Hz** + event | see below |

**Low frequency is a requirement, not a guideline.** These share the socket with
30 Hz teleop frames; the ceilings are hard (`mnesis_canonical.PS_MAX_HZ`, checked
by `validate_ps_stream`). A producer with several observations **batches them
into one `semantic_label`** — the body carries an array — instead of bursting.
The `scene_graph` band is a ceiling with a nominal floor: change-driven means
**silence is legal** when the map does not change, so consumers must not
implement a 1 Hz heartbeat off it.

A `robot`-sourced label never travels on `semantic_label`: it is already on the
authoritative side.

#### `colocalization` body

```jsonc
{
  "map_id": "lab_bench_a",
  "state":  "ok",                     // ok | stale | lost
  "T_map_headset": { "t": [...], "q": [...] },   // T_map←headset
  "computed_at_ns": 1785196800940000000,
  "quality": { "rmse_m": 0.014, "inlier_ratio": 0.91, "match_count": 428 },
  "event":  "colocalization_stale",   // only with state stale | lost
  "reason": "tracking recovered; extrinsic not re-solved"
}
```

- `T_map_headset` transforms a point in the headset frame into the map frame — it
  is what lets the headset publish labels in `frame_id: "map"` at all. **Required
  when `state == "ok"`, and MUST be omitted when `state == "lost"`**: an identity
  transform published as a stand-in silently parks every headset label at the map
  origin. `computed_at_ns` is required whenever it is present — the age of an
  alignment is what makes it trustworthy.
- `quality` is required when `state == "ok"`; an extrinsic without a quality
  figure cannot be gated on.
- **`colocalization_stale` is not a fourth message type.** The event is this
  message with a non-`ok` state, so alignment health has exactly one place to be
  read from.

### Golden samples

`examples/semantic/` carries one validated sample per message plus the three
boundary cases the consumers asked for: `disputed`, `stale`, and
`source: "headset"`.

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
- **`observation.hand.*` (C11, additive-only, `experimental`)**: old data without these keys is **valid**. Consumers MUST treat a missing hand key as "no hand data" and MUST NOT substitute zeros. The vector length is not fixed by the schema — resolve `observation.hand.layout` through the skeleton registry before reading. See §Hand keypoints.
- **`observation.gripper[.left|.right]` (additive-only)**: the observation-side gripper closedness. **Same direction as `action.gripper`** — `0.0` = fully open, `1.0` = fully closed — so within one frame `action.gripper` and `observation.gripper` share a single, unambiguous scale (both `0.3` = the same "mostly open" state). Absence means no gripper observation (NOT `0.0`). Optional across all profiles; `.left` / `.right` are for bimanual `robot_v2`.

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
| `observation.hand.*` | (extra columns) | human-hand keypoints (retargeting input) | ℹ️ Canonical-only for now; SI m + quat `{x,y,z,w}`. Shares the ⚠️ frame + quaternion items below |
| `profile` / `embodiment_id` | (metadata) | — | ℹ️ Canonical-only profile mechanism |
| `source.device` / `source.modality` | (metadata) | embodiment tag / dataset metadata | ⚠️ map to GR00T embodiment tag — mapping table 待对齐 |
| `tracking_state` | (extra column) | — | ℹ️ Canonical-only QA flag |

**Open items (⚠️ 待对齐 Parthenon `03 §3.2` — do NOT freeze unilaterally):**
1. **Quaternion order.** Canonical is `{x,y,z,w}` scalar-last (ARCore); Isaac/USD convention is `{w,x,y,z}` scalar-first. A reference export adapter exists — `mnesis_canonical.isaac.to_isaac` / `from_isaac` (reorders the pose-block quaternion, exact round-trip). It is **adapter-only; the wire format is unchanged.** Whether the canonical wire ever switches order is the only open call here.
2. **World frame / up-axis & handedness.** Both are right-handed, but ARCore is Y-up while Isaac Lab is typically Z-up. The adapter exposes an optional `world_transform` hook that **defaults to identity** (it does not guess a transform); pin the canonical world frame + the concrete GR00T export transform with the authority.
3. **Action rotation representation.** Canonical `action` rotation is axis-angle (rad); the adapter passes `action` through **verbatim** (do not consume the exported `action` as Isaac-native yet). Confirm GR00T/Isaac action-space expectation before locking.
4. **Embodiment tagging.** Exact `source.device`/`source.modality` → GR00T embodiment-tag mapping (not yet implemented in the adapter).

Until these are resolved, conversion stays a **documented adapter concern**, not a wire-format change — the Canonical fields above are stable.

## Embodiment registry — `capture` section (additive, v0.5+)

The embodiment registry (`embodiments/<id>.json`, schema
`embodiments/embodiment.schema.json`) is the **single source of truth** for a
robot's identity, kinematics, and — as of v0.5 — its **capture-side defaults**.
Both additions are **optional and additive**: registry entries without them keep
validating, and consumers that don't read them are unaffected. The point is
"switch machine → already configured": a device swaps embodiment id and picks up
frame rate, camera rig, gripper semantics, teaching mode, and calibration needs
without each consumer hard-coding them.

### `capture` (optional object)
| Key | Type | Meaning |
|---|---|---|
| `default_fps` | number > 0 | Default recording frame rate (fps). |
| `max_duration_s` | number > 0 | Recommended per-episode duration cap (seconds). |
| `cameras` | array | Default camera rig: each `{ name, resolution:[w,h], fps? }`. `name` matches `observation.images.<cam>`. |
| `gripper_capture` | object | `{ mode: "continuous"\|"binary"\|"none", normalized_range?:[0,1] }`. Physical stroke stays in `gripper_range`, not here. |
| `demonstration_modes` | array | Supported teaching modes — subset of `kinesthetic`, `leader_follower`, `teleop_only`. Consumers switch capture UI on this. |
| `calibration` | object | `{ hand_eye_required: bool }` — whether camera↔arm extrinsic calibration is required before a valid session. |

### `capture_profiles` (optional array)
Named presets a registry entry may carry several of; a consumer selects one by
`name` to configure a session: `{ name, task?, fps?, cameras?, annotation_template? }`.
`cameras` is a subset of `capture.cameras` names; `annotation_template` references
a taxonomy id (e.g. `manipulation_v1` → `taxonomies/manipulation_v1.json`).

### Two-machine truth (v0.5)
| Machine | fps | cameras | gripper | demo mode | hand-eye |
|---|---|---|---|---|---|
| `so_arm101` (SO-ARM101) | 30 | front + wrist @640×480 | continuous | `leader_follower` | not required |
| `airbot_play` (AIRBOT Play) | 30 | wrist @640×480 + front @1280×720 | continuous | `kinesthetic` (gravity-comp drag) | not required |

### Consumer upgrade path (ambrosia / airbot capture ends)
Additive, so no forced migration; adopt lazily:
1. **Read on change:** on embodiment select, read `capture` (fall back to your
   current defaults when absent) to set fps / camera rig / duration cap.
2. **Gripper UI:** branch on `gripper_capture.mode` (`continuous` slider vs
   `binary` toggle vs hidden).
3. **Teaching UI:** show the capture flow implied by `demonstration_modes`
   (leader-follower pairing for SO-ARM101, gravity-comp drag for AIRBOT Play).
4. **Calibration gate:** if `calibration.hand_eye_required` is true, block record
   until calibration is present.
5. **Presets:** offer `capture_profiles` by `name`; a missing/empty list means
   "no presets — use `capture` defaults".

## Versioning
- Spec is versioned (SPEC_VERSION v0.2). Additive fields = minor; breaking field change = major + migration note. `__version__` in the package mirrors this.
- **Field-level status.** Each field carries a status: one of
  `experimental`, `stable`, or `deprecated`. The authoritative value is the
  `x-status` key in `canonical_frame.schema.json` (mirrored as the `[experimental]`
  / `stable` / `[deprecated]` prefix in `SPEC.md` §Fields and in `schema.py`).

  | status | meaning | commitment |
  |---|---|---|
  | `experimental` | Adopted into the standard, can be produced and validated now | **May be renamed or reshaped before going `stable`**; such a change is not counted as breaking |
  | `stable` | Frozen | Extendable only additively; rename requires a major bump |
  | `deprecated` | Being retired | Must carry `deprecated_since` + migration guidance; removed only with a major bump |

  A field marked **`[experimental]`** in §Fields is standardised and validated, but
  may still be renamed or reshaped before it goes `stable`, and such a change is
  not counted as breaking. All other fields are `stable`: frozen, extendable only
  additively, renameable only with a major bump. This exists so a field that is
  *already in production somewhere* can be brought inside the standard immediately —
  rather than staying non-standard for weeks while its final shape is settled —
  without that speed implying a freeze. A downstream consumer that wants to reject
  non-frozen data can pass `--strict-stable` to the validator (see CLI).

## Conformance
A producer is conformant if every line passes `mnesis_canonical.validate_frame` and
`frame_index` is strictly increasing per episode (`validate_frames`).