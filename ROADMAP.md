# ROADMAP — mnesis-canonical

> **做什么、什么顺序。** 本仓的开放标准是 Mnesis 数据飞轮的"USB-C"——一个格式所有采集面产出、Ambrosia 平台摄入。
> 跨仓全局路线图见 Parthenon `ROADMAP.md`。

---

## 当前状态

- **v0.5.0**（`__version__` = `pyproject` = `CHANGELOG.md` preamble）
- 核心：typed `CanonicalFrame` + validate + JSONL I/O + LeRobot/Isaac 适配器 + manifest + Device Adapter SDK
- 采集面：Iris ✅（真机验过）· Daedalus T3 ✅（上传器已做，缺 `frames.zip`）· Eidolon MI-1 ⛔（唯一缺口）

---

## 已完成里程碑

| 里程碑 | 内容 | Issue |
|---|---|---|
| D-9a · Profile 机制 | v0.2 schema，`ego_v1` / `robot_v2`，additive-only | #38 |
| D-13 · `action.gripper` | 帧级可选夹爪通道，归一化 `[0,1]` | #31 |
| D-18 · C8 gripper observation | `observation.gripper[.left|.right]` + C3 v1.6 相机协商/视频能力 | #38 |
| D-18 · C3 v1.7 WebRTC 信令 | `video_offer` / `video_answer` / `video_ice` 三消息 | #60 |
| C11 结案 · `observation.hand.*` | 七字段 + 骨架登记表（`mediapipe_hand_21` / `webxr_hand_25` / `openxr_hand_26`） | #68 |
| 铁律升格 · 缺失=未知禁带内哨兵 | `SPEC.md` §Conventions | #70 |
| 字段级 status · `experimental`/`stable`/`deprecated` | `SPEC.md` §Versioning | #70 |
| C12 双端语义契约 PS0 | `ObservationLabel` / `scene_graph` / 三个 8442 消息 + 分类登记表 | #77 |
| 版本号一致性门禁 | `scripts/version_check.py` 三处一致 | #82 |
| T1 快路径试点 | 无状态检查挪到托管 runner | #101 |
| T5-std 发布清单 | `RELEASE_CHECKLIST_v1.0.md` 推上 canonical main | #99 |
| 扩展命名空间 | `x-<vendor>.*` 保留段 + 未知键警告 + 扩展登记表 | #69 |
| 版本号三处一致门禁（收紧） | `__init__.py` / `pyproject.toml` / `CHANGELOG.md` 三处联动校验 | #100 |
| C1-vNext · manifest 溯源段 | `schema_version`/`capture_app`/`app_version`/`git_sha`/`device_id`/`session_id`/`calibration_ref` | #113 |
| embodiment registry · `ego_human_5cam_v1` | 新 embodiment profile + `cameras[]` 加 `lens`/`fov_deg` | #119 |
| manifest 通用 `sidecars[]` | 1000Hz IMU / 4ch 音频等旁路数据的合法落盘位置（对应 Parthenon C2 media.tar） | #116 |

---

## 待办（按优先级）

### P0 — Eidolon MI-1（全网飞轮闭环最后一块）

Quest→Canonical 导出器，补齐第三采集面。手部/头显位姿 → `head_pose_SE3`，`source.device=quest`。

**依赖**：Eidolon 侧实现，本仓提供 canonical schema 支持。

### P1 — `spatial_anchor_pose_SE3` 采集端落地

已新增可选字段（anchor 在世界系的位姿）。采集端若能定位 anchor 应填充；填不了就省略（不影响其他校验）。

**依赖**：Iris / Eidolon 采集端支持。

### P1 — C6 跨设备时间同步

每 session 记录一次实测时钟偏移（设备 vs 参考钟）。做多设备融合 / 遥操作因果分析前必须。
落地形态为 manifest 可选 `clock` 段：`source`（`ptp`/`tsf`/`ntp`/`none`）+ `refDeviceId` +
`offsetNs` + `estErrorNs`（草案原文的 `clock_offset_ns` 不进 wire），见 `SPEC.md` §Clock synchronisation。

**状态**：实现已在 [PR#131](https://github.com/Mnesis-Labs/mnesis-canonical/pull/131)，CI 绿，待 Muso 拍板合并（`needs:muso-decision`）。

### P1 — C9 相机内参一等字段

`camera_intrinsics`（fx/fy/cx/cy/畸变模型/分辨率）成为 canonical 一等字段。

**状态**：实现已在 [PR#127](https://github.com/Mnesis-Labs/mnesis-canonical/pull/127)，CI 绿，待 Muso 拍板合并（`needs:muso-decision`）。

### P1 — C1 ego_multicam_v1 · 多相机 ego 图像键集

单键 `observation.images.ego` 装不下 5 路相机，新增 profile 支持多路。

**状态**：实现已在 [PR#128](https://github.com/Mnesis-Labs/mnesis-canonical/pull/128)，CI 绿，待 Muso 拍板合并（`needs:muso-decision`）。

### P1 — canonical 发 PyPI + 语义化版本

`pip install mnesis-canonical` 目前仍 404，三个消费仓只能装 `git+...@main`。

**状态**：发布链路本身（`workflow_dispatch` + 托管 runner + PyPI Trusted Publishing）已在 [PR#130](https://github.com/Mnesis-Labs/mnesis-canonical/pull/130)，CI 绿，待 Muso 拍板合并。**合并后仍差一个仓外人工步骤**：需要有 PyPI 账号权限的人去 <https://pypi.org/manage/account/publishing/> 建 pending publisher（project `mnesis-canonical` / owner `Mnesis-Labs` / workflow `release.yml`），agent 结构上做不到这步。

### P2 — C8 space_id · 多设备同空间 episode 合并

Parthenon delta 卡 [Parthenon#507](https://github.com/Mnesis-Labs/Parthenon/issues/507) 已关闭，但本仓此前从未开对应实现卡——C2/C6/C9 都有卡在跑，C8 掉了。

**状态**：2026-08-19 补开 [#135](https://github.com/Mnesis-Labs/mnesis-canonical/issues/135)，尚未排期。

### P2 — C7 数据集导出格式契约

Ambrosia S6-3 落地时定契约，LeRobot/Isaac 导出成为稳定契约。

**Owner**：Ambrosia（复用本仓 `to_lerobot`）。

### P3 — body-pose 骨架（C11 另一半）

`skeletons/` 的 `kind` 已预留 `"body"`。待 Eidolon/训练侧提出真实需求再立卡。

---

## 跨仓"会师点"（投资人可演示）

Eidolon MI-1 ✅ + Ambrosia S6（收 3 面 + robot 忠实回放 + LeRobot 导出）✅ + Daedalus（frames.zip + C5 发版）✅

→ 一次联测：手机/Quest/机器人三面同屏入库 → 数据集 → 忠实回放 → 一键导出 LeRobot。

---

## Parthenon Feature ID 映射

> 来源：Parthenon `cockpit/data/roadmap-spine.json`（读取 2026-08-08，2026-08-19 复核刷新）。
> 本仓在 Parthenon 全局路线图中的工作映射如下。

### 本仓为 Owner 的 Feature

| Feature ID | 标签 | Track | 时间 | 对应本仓工作 |
|---|---|---|---|---|
| `F-T2-comms-c3-xr-bridge` | C3 夹爪通道 + 双臂 xr_bridge v2 + 相机控制 | T2-comms | Next | C3 v1.6 相机协商 + v1.7 WebRTC 信令（#60）+ gripper observation |
| `F-T2-percep-ps0` | PS0 语义契约先行 | T2-percep | Now | C12 双端语义契约（#77） |
| `F-T3-argus-v0-spans` | D-12 v0.3 spans 区间标注契约 | T3-argus | Done | events/spans 标注 schema（已落地） |
| `F-T4-contract-contracts-lock-sha256` | 消费仓 contracts.lock + CI sha256 校验落地 | T4-contract | Now | `contracts/contracts.lock` + `contracts_check.py` |
| `F-T5-std-consumer-pin` | 三消费仓装法改版本钉 `mnesis-canonical==X.Y.Z` | T5-std | Next | 版本号一致性门禁 + `pyproject` pin 指南 |
| `F-T5-std-s9-xrobotoolkit-pickle` | S9 XRoboToolkit pickle→canonical 导入器 | T5-std | Next | `importers/xrobotoolkit.py` |
| `F-T5-std-motion-spec` | canonical 标准运动启动 | T5-std | Next | 本仓 roadmap 待立卡（待 Parthenon 侧开 delta） |
| `F-T4-contract-canonical-provenance` | C1-vNext manifest 溯源段 | T4-contract | Now（实为 Done） | manifest 加 provenance 字段（#113，已合并）+ embodiment registry 扩展（#119，已合并） |
| `F-T4-contract-canonical-schema-expansion` | Canonical schema 扩展（C2/C6/C8/C9） | T4-contract | Now | 对应 Parthenon delta #505(C6)/#506(C9)/#507(C8)/#508(C2)；本仓卡 #118(PR#131)/#117(PR#127)/#135(C8 新开)/#116(已合并) |
| `F-T5-std-canonical-release-gate` | canonical 发版门禁与版本号一致性 | T5-std | Now | 版本号三处一致门禁（#100，已合并）+ PyPI 发布链路（#109，PR#130 待合并） |

### 本仓为参与方的 Feature（依赖链）

| Feature ID | 标签 | Owner | 本仓角色 |
|---|---|---|---|
| `F-T5-std-canonical-pypi` | canonical PyPI 发布 | Parthenon | 提供 `mnesis-canonical` 包（依赖 F-T5-std-consumer-pin / F-T5-std-motion-spec） |
| `F-T4-contract-daedalus` | Daedalus 侧契约对齐 | Mnesis-Daedalus | 本仓 `contracts.lock` sha256 校验是前置依赖 |
| `F-T4-contract-iris` | Iris 侧契约对齐 | Mnesis-Iris | 同上 |
| `F-T4-contract-eidolon-lock` | Eidolon 侧契约对齐 | Mnesis-Eidolon | 同上 |
| `F-T4-roadmap-amnesty` | 五仓文档大赦 | Parthenon | 本仓 #102 即本 Feature 的 canonical 侧落地 |

### 未映射（待 Parthenon 侧开 delta）

| 本仓工作 | 说明 | 建议 Feature |
|---|---|---|
| C1 帧 schema 主体 + `canonical_frame.schema.json` | 全仓基石，Parthenon spine 中未单列 | 归属 `T2-comms` / `T4-contract` 底座，建议 F-T4-contract 下增设 `F-T4-contract-c1-schema` |
| 骨架登记表（`skeletons/`） | C11 结案配套 | 归属 `F-T2-percep-ps0` 或新开 `F-T2-comms-c11-skeleton-registry` |
| LeRobot/Isaac 适配器 | `to_lerobot` / `to_isaac` | 归属 `T5-std` 底座，建议 `F-T5-std-adapters` |
| Device Adapter SDK | `mnesis_canonical.sdk` | 归属 `T2-comms`，建议 `F-T2-comms-adapter-sdk` |
| 文档大赦（ROADMAP/PRD/DEV_GUIDE 收敛） | 本卡 #102 | 归属 `F-T4-roadmap-amnesty` |

**已并入 `F-T4-contract-canonical-schema-expansion`（Parthenon spine 已登记，见上表）**：C1-vNext manifest 溯源段（#113，已合并，另见 `F-T4-contract-canonical-provenance`）、C6 clock（PR#131 待合并）、C9 camera_intrinsics（PR#127 待合并）、C2 media.tar/sidecars（#116，已合并）。C8 space_id 此前在这四项里唯一没有本仓实现卡，2026-08-19 补开 #135。