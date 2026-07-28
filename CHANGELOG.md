# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [SemVer-of-the-schema](README.md#compatibility-commitment)
— the **package version** (this changelog) and the **schema version** (SPEC.md §Versioning)
are decoupled:

> **Package 0.3.0** introduces the **profile mechanism** (v0.2 schema) for additive
> schema evolution. `ego_v1` = v0.1 backward-compatible default; `robot_v2` adds
> variable-length vectors, open camera keys, and optional `eef_pose`. All existing
> data and examples validate without modification.

## [Unreleased]

### Added

- **双端语义契约 C12 / PS0（Parthenon#58 · Daedalus ADR-004 · #77 · Muso 拍板）**。
  机器人端（Daedalus）与头显端（Eidolon）产出的是同一种东西，所以它在 canonical
  定义一次，两端只读消费（照 C1 视频信令先例）。**本仓只定契约不写实现**：融合归
  Daedalus，头显消费归 Eidolon。

  - `ObservationLabel` —— 两端产出的统一观测标签：`label_id` / `class_id` /
    `confidence` / `source` / `sensor?` / `frame_id` / `pose` / `extent?` /
    `observed_at_ns`。
  - `scene_graph` —— 融合产物（机器人端权威）：`map_id` / `revision` /
    `updated_at_ns` / `labels[]`，label = ObservationLabel + `state` /
    `witnesses` / `dispute?`。
  - 三个 8442 WS 消息，**信封 v1 = C3 公共头 `{type,seq,ts,body}` 原样**：
    `semantic_label`（上行，事件驱动）、`scene_graph`（下行，1–5 Hz 变更驱动）、
    `colocalization`（双向，低频 + 事件）。
  - `taxonomies/object_class_v1.json` + `taxonomy.schema.json` + **分类登记表
    加载 API**（`list_taxonomies` / `load_taxonomy` / `list_term_ids`，root +
    package 双份，与 `skeletons/` 同构）—— `class_id` 的唯一取值域。
  - 校验器 `validate_observation_label` / `validate_scene_graph` /
    `validate_ps_message` / `validate_ps_stream`，JSON Schema
    `mnesis_canonical/semantic.schema.json`（头显端 JS 侧校验用），golden 样本
    `examples/semantic/`（含 `disputed` / `stale` / `source:"headset"` 三个边界样本）。

  **`source` 枚举第一天就含 `headset` / `human`**，尽管头显识别（PS4）与人裁决是
  backlog —— 后补枚举值是契约变更，每个硬编码二值分支的消费方都要回头改。

  **对草案的三处收紧**：① `observed_at` 浮点秒 → **`observed_at_ns` 整数纳秒**，
  与 `t_ns` / `t_hw_ns` / C3 `ts` 统一（一个 wire 格式两种时间单位迟早出转换 bug）；
  ② `frame_id` 收成闭集 `{map}`，把「不接受局部系」从散文变成可校验事实；
  ③ `confidence` 必填 —— 没写置信度的输入没法融合。

  **低频是硬要求**：`PS_MAX_HZ` 天花板由 `validate_ps_stream` 实测校验，多条观测
  批进一条消息而不是连发 —— 这三个消息与 30 Hz teleop 帧共用同一条 socket。
  变更驱动 = 没变更就静默，1 Hz 是标称下限不是心跳。

  `contracts/` 与 `contracts.lock` **本次零改动**：PS 消息不改 C1 帧、不改 C3 既有
  消息。

- **手部关键点 `observation.hand.*`（C11 结案 · Parthenon#47 / #68 · Muso 拍板）**。
  七个**可选 / additive** 字段，把骨架级手部数据收进单一标准，取代 Iris 从 D-13 起
  私产的四个非标字段。老数据零破坏：不带这些键的帧校验行为完全不变。

  - `observation.hand.left` / `.right` —— 关节**位置**，展平 `[x,y,z,…]`（米）。
    **变长**：长度 = `3 × K`，`K` 由 `observation.hand.layout` 经新增的**骨架登记表**
    （`skeletons/<id>.json`）解析。这与 `embodiment_id` 的 `joint_names` 定义
    `observation.state` 长度是同一机制 —— 标准里只保留一种「长度在别处声明」的做法。
  - `observation.hand.left.rot` / `.right.rot` —— 关节**朝向**，展平四元数 `{x,y,z,w}`，
    长度 `4 × K`；仅原生提供朝向的来源填。
  - `observation.hand.layout` + `observation.hand.frame` —— **有关键点时必填**。
    `frame ∈ {world, head_anchored, hand_local}` 是「这是 2.5D 近似而非真 3D」
    这条警告的**机器可读形式**：消费方按 `frame == "world"` 过滤，而不是去认某个
    source 字符串。
  - `observation.hand.source` —— 溯源标签（开放集），**不承载几何语义**。

  **为什么不用定长 63**：`63 = 21 × 3` 只在所有人都是 MediaPipe 时成立。
  Eidolon C2 走 WebXR Hand Input（25 关节，OpenXR 侧 26）且带逐关节朝向，而
  C11 的立卡动机 —— xMimic 类骨架 retargeting —— 吃的正是朝向。定长会逼 XR 产出方
  要么降采样丢朝向、要么另造字段。

  **`hand_pose`（128 floats）不进 wire**：它是前两者的派生投影，且用
  `leftPresent` 标志位 + 补零编码「手不在」，与下面的铁律冲突。派生形状归导出器。

- **骨架登记表 `skeletons/`**（root + package 双份，与 `embodiments/` 同构）
  + 加载 API `list_skeletons` / `load_skeleton` / `joint_count`。
  已注册：`mediapipe_hand_21`（21 关节，无朝向，`stable`）、
  `webxr_hand_25` / `openxr_hand_26`（带朝向，`experimental` —— 待 Eidolon 按真机实现核对）。
  加一个布局是一次登记表 PR，不是 schema 变更。`kind` 已预留 `"body"` 给 C11 的另一半。

- **迁移 `mnesis_canonical.migrate_hand_v0[_frames]` + CLI `migrate` 子命令**。
  重写 Iris 存量数据：三个字段改名、丢弃派生的 `hand_pose`、补上
  `layout=mediapipe_hand_21` + `frame=head_anchored`（把原本只存在于
  `HandWorldTransform.kt` 类注释里的 2.5D 说明变成数据）。
  **校验器只认新名，不认双名** —— 标准里的别名从来不会死。

  ```bash
  python -m mnesis_canonical migrate episodes/ep_0/data.jsonl --out episodes/ep_0/data.jsonl
  ```

- **`SPEC.md` §Conventions 新增铁律：缺失 = 未知，禁带内哨兵**。
  不得用 `0` / 零向量 / `-1` / `NaN` / `""` 编码「未知 / 不适用」，不知道就省略该键；
  消费方不得给缺失的可选字段填默认值。这条本来就是 `action.gripper` 缺失 ≠ `0.0`
  和 `spatial_anchor_pose_SE3` 缺失即跳过校验背后的同一条原则，现在升成通则，
  以后加字段不必重新论证一遍。

- **`SPEC.md` §Versioning 新增字段级 status**（`experimental` / `stable`）。
  `experimental` 字段已标准化、已校验，但 **stable 前可改名/改形，且不算破坏性变更**。
  这让「已经在产的字段当天进标准」和「不仓促冻结形状」同时成立 —— 手部字段是第一个用例。

### Fixed

- **`spatial_anchor_id` 的身份来源改为 anchor 自己**（Parthenon#26 拍板 B；破坏性放宽）。
  0.4.0 引入的冲突校验（#47/PR#55）用 `head_pose_SE3` 的平移分量当 anchor 的身份，
  1mm 容差内不同即判 `conflicting spatial_anchor_id`。但 `spatial_anchor_id` 命名的是
  **世界系里的固定点**，`head_pose_SE3` 是**观察者的位姿** —— 后者在 ego 采集里必然移动，
  这正是 ego 采集的定义。两者绑定等于「只有操作者一动不动时才能引用某个 anchor」，
  **任何戴着头显走动并引用同一 anchor 的真实 episode 都会在 ingest 被拒**
  （mnesis-ambrosia `POST /api/episodes` → 422，实测）。

  现在：冲突只对新增的可选字段 `spatial_anchor_pose_SE3`（anchor 自身的世界系位姿）比较。
  该字段缺失时**跳过一致性检查**，不再回落到 `head_pose_SE3`。悬空/空串引用检测不变。

  迁移：采集端若能定位 anchor，请填 `spatial_anchor_pose_SE3`；填不了就不填 —— 只是失去
  这一项交叉校验，不影响其他任何校验。已入库数据无需改动。

### Added

- **`spatial_anchor_pose_SE3`（可选）** —— anchor 在世界系的位姿 `[tx,ty,tz, qx,qy,qz,qw]`。
  见上条。

### Added

- **Optional `observation.gripper` channel** (additive-only; Parthenon#20 拍板 A).
  Observation-side gripper **closedness** as a first-class `float` in `[0.0, 1.0]`,
  **`0.0` = 完全张开 (fully open), `1.0` = 完全闭合 (fully closed)** — direction
  **identical to `action.gripper`** and to the C3 xr_bridge wire field
  `arms[].gripper`. `observation.gripper` (single/main, any profile) and
  `observation.gripper.{left,right}` (bimanual `robot_v2`). Absence = no gripper
  observation (NOT `0.0`). Frames without a gripper key validate unchanged.
- **D-18 — C8 gripper channel** (v0.2 schema, additive-only). Optional
  first-class gripper opening as a continuous scalar in `[0, 1]` (0=closed,
  1=open): `observation.gripper` (single/main, any profile) and
  `observation.gripper.{left,right}` (bimanual robot_v2). Semantics align 1:1
  with the C3 xr_bridge wire field `arms[].gripper`. Frames without a gripper
  key validate unchanged.
  - `GRIPPER_KEYS`, `GRIPPER_MIN`, `GRIPPER_MAX` constants; `CanonicalFrame`
    extended with `gripper` / `gripper_left` / `gripper_right`.
  - JSON Schema `observation.gripper[.left|.right]` (`number`, `[0,1]`);
    validator range/finite check.
  - `examples/episode_gripper` — robot_v2 teleop example carrying a gripper.
  - `tests/test_gripper_observation.py` conformance + an `action`/`observation`
    same-frame co-existence (same direction) case.

### Changed

- **C3 xr_bridge — `arms[].gripper` endpoint definition made explicit** (contract
  clarification; wire version unchanged at v1.5). The wire field was documented
  only as 「夹爪开度 [0.0, 1.0]」 with **undefined endpoints**; it is now
  「夹爪**闭合程度** [0.0, 1.0]：`0.0` = 完全张开，`1.0` = 完全闭合」, aligned
  with canonical `action.gripper` / `observation.gripper`. A consumer note flags
  that existing implementations may have read the opposite direction before this
  clarification and must re-check on integration. `contracts.lock` regenerated.

- **Issue #41 — Embodiment registry `capture` section + `capture_profiles`
  presets** (additive-only; Muso 站会直派 2026-07-22). The embodiment registry
  now carries optional capture-side truth so a device reconfigures by embodiment
  id instead of each consumer hard-coding it. Existing registry entries without
  these keys validate unchanged (existing tests untouched).
  - `capture` (optional object): `default_fps`, `max_duration_s`,
    `cameras[{name, resolution, fps?}]`, `gripper_capture{mode, normalized_range?}`,
    `demonstration_modes` (⊆ `kinesthetic`/`leader_follower`/`teleop_only`),
    `calibration{hand_eye_required}`.
  - `capture_profiles` (optional array): named presets
    `{name, task?, fps?, cameras?, annotation_template?}`; a registry entry may
    carry several.
  - Real values for `so_arm101` (leader-follower, front+wrist @640×480) and
    `airbot_play` (kinesthetic gravity-comp drag, wrist @640×480 + front @1280×720).
  - `embodiment.schema.json` (root + package copies in sync); SPEC.md
    §"Embodiment registry — capture section" with the consumer upgrade path;
    conformance `tests/test_capture.py`.

## [0.4.0] — 2026-07-21

### Added

- **D-13 前置 — Optional `action.gripper` field** (additive-only; Parthenon#16
  问题二 = A). Frame-level optional `float` gripper channel, **normalized**
  `[0.0, 1.0]` (`0.0` = fully open, `1.0` = fully closed). Absence means the
  source provides no gripper info — semantically **distinct from `0.0`** — and
  consumers must handle a missing field as "no gripper". Out-of-range or
  non-numeric values are rejected with a clear error; the `action` vector length
  is unchanged (gripper is an independent field, not a widened `action`).
  - `CanonicalFrame.action_gripper` (`to_dict()` emits `"action.gripper"` only
    when non-None; `from_dict()` reads it, absent → None).
  - `validate_frame` range/type check; `canonical_frame.schema.json` optional
    `action.gripper` property (`0.0 ≤ x ≤ 1.0`).
  - SPEC.md field row + compatibility note; CONTRACTS.md C1 change record.
- Existing data without `action.gripper` validates unchanged (regression covered).
  - `tests/test_gripper.py` conformance cases.
- **D-18 — C3 xr_bridge v1.6** (contract, additive). Camera-control negotiation
  (`C3_CameraControl` headset→robot `{camera_id,width,height,fps,bitrate,codec}`,
  OPEN_CAMERA-style over our ws envelope + `C3_CameraStatus` reply) and video
  transport capability declaration (`C3_Info.video_capabilities`,
  `transports: webrtc|mjpeg`, reserved for the DQ-1 WebRTC line). `≤v1.5`
  clients ignore the new messages/field — wire format unchanged. Specified in
  `contracts/XR_ROBOT_CONTRACT.md` + `contracts/xr_bridge_SPEC.md`; consumer
  `contracts.lock` upgrade path documented in `CONTRACTS.md`.
  - `contracts.lock` regenerated; `tests/test_contracts.py` pins the spec.

## [0.3.0] — 2026-07-21

### Added

- **D-9a — Profile mechanism** (v0.2 schema, additive-only). Frame top-level
  optional `profile` (default `ego_v1`) and `embodiment_id` fields. v0.1 frames
  without these fields pass all validation unchanged (regression covered).
  - `PROFILES`, `DEFAULT_PROFILE`, `ROBOT_V2_VARIABLE_VECTORS` constants.
  - `required_keys_for_profile()` helper function.
- **D-9a — robot_v2 profile**: `observation.state` and `action` are
  variable-length float[N] (no fixed-size check); `observation.images.<cam>`
  open key set (at least one required, no single camera mandatory); optional
  `observation.eef_pose.{left,right}` (each float[7]).
- **D-9a — `examples/episode_dual_airbot`** — robot_v2 profile example with
  14-DoF dual-arm state/action, wrist_left/wrist_right cameras, and optional
  eef_pose left/right. Validates via `validate_frames` (strict).
- **SPEC v0.2** — rewritten with profile table, robot_v2 field documentation,
  backward-compatibility guarantee.
- **JSON Schema v0.2** — `$id` bumped to `v0.2.json`; conditional validation
  via `if/then/else` for profile-specific requirements.

### Changed

- `CanonicalFrame` dataclass extended with `profile`, `embodiment_id`,
  `observation_images` (extra camera keys), `eef_pose_left`, `eef_pose_right`.
- `REQUIRED_KEYS` split into `_REQUIRED_KEYS_EGO_V1` and `_REQUIRED_KEYS_ROBOT_V2`;
  base `REQUIRED_KEYS` constant kept as ego_v1 for backward compat.

## [0.2.0] — 2026-07-11

### Added

- **C1 — JSON Schema** (`canonical_frame.schema.json`, Draft 2020-12) with optional
  `jsonschema` backend (`validate_frame_jsonschema`). Bundled as a language-agnostic
  standard contract.
- **C2 — Validate CLI** (`python -m mnesis_canonical validate <path>`). Prints
  `total=.. valid=.. errors=..` summary, exit code 0 / 1 / 2 for CI gating.
- **C3 — LeRobot columnar adapter** (`to_lerobot` / `from_lerobot`). Pure transpose
  with no renaming or unit change; exact round-trip.
- **C4 — Multi-surface examples** (`examples/episode_quest`, `examples/episode_robot`)
  covering all three capture surfaces (phone, quest, robot). Strict-vocab validation
  guard against unknown `source.device` / `source.modality`.
- **C5 — Isaac / GR00T field mapping** documented in SPEC §Compatibility. Adapter
  does not change the wire format.
- **F1 — Episode manifest** (`build_manifest`, `manifest_for_episode`, `write_manifest`
  + `manifest` CLI subcommand). Produces `manifest.json` with `frameCount`,
  `episodeIndex`, `jsonlSizeBytes`, `videoPath`, `videoSizeBytes`, `durationMs`.
- **F2 — Isaac/GR00T export adapter** (`to_isaac` / `from_isaac`). Reorders
  quaternions scalar-last ↔ scalar-first; optional `world_transform` hook (defaults
  to identity). Exact round-trip. Adapter-only — wire format unchanged.
- **CONTRACTS.md** — cross-repo contract registry linking Mnesis-Iris / Eidolon /
  Daedalus / Ambrosia.
- **S2-1 — PEP 561 type distribution** (`py.typed` marker + `pyright` dev dependency).
  All public functions already annotated; zero pyright errors.

### Changed

- **Refactored to slim standard library** — removed demo/viz/synth machinery, keeping
  only the pure standard-library core: schema, validator, I/O, adapters, manifest,
  CLI. Zero runtime dependencies.
- LF-only `.gitattributes` for `*.jsonl`, `*.json`, `*.py`, `*.md`, `*.toml` to
  keep wire formats byte-stable across platforms.
- Version bumped from `0.1.0` → `0.2.0` (package); schema version stays `v0.1`.

### Fixed

- `write_jsonl` / `write_manifest` now write explicitly with `LF` newline
  (cross-platform determinism).

### Security

- No runtime dependencies in the core package (optional `jsonschema` in extras).

## [0.1.0] — 2026-06

### Added

- Initial scaffold: `CanonicalFrame` dataclass, `REQUIRED_KEYS`, `VECTOR_LENGTHS`,
  `validate_frame`, `validate_frames`, `read_jsonl`, `write_jsonl`.
- `examples/episode_0` (phone / ego_human).
- Dual-timestamp design, quaternion `{x,y,z,w}` scalar-last, relative-delta action.

[0.4.0]: https://github.com/Mnesis-Labs/mnesis-canonical/releases/tag/v0.4.0
[0.3.0]: https://github.com/Mnesis-Labs/mnesis-canonical/releases/tag/v0.3.0
[0.2.0]: https://github.com/Mnesis-Labs/mnesis-canonical/releases/tag/v0.2.0
[0.1.0]: https://github.com/Mnesis-Labs/mnesis-canonical/releases/tag/v0.1.0