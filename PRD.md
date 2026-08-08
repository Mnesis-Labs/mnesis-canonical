# PRD — mnesis-canonical

> **做成什么样（验收判据）。** 本仓是 Mnesis 数据飞轮的开放层（Open-Core，Parthenon `01 §2`）：schema + 参考校验器 + 设备抽象 SDK 开源成为事实标准；专有核心（高保真数据、4DGS 物理、评测）在 Ambrosia。

---

## 1. 产品定位

**Canonical Frame Schema** —— "USB-C of robot-trainable data"：一个格式所有采集面（手机 / Quest / 机器人）产出，Ambrosia 平台摄入。Apache-2.0，可自由采用。

**核心用户**：
- 采集面开发（Iris / Eidolon / Daedalus）：产数据
- 平台开发（Ambrosia）：校验 / ingest
- 训练管线：消费 LeRobot / Isaac 格式

---

## 2. 核心能力验收

### 2.1 帧格式（C1）

| 能力 | 验收 |
|---|---|
| typed `CanonicalFrame` | 所有字段类型明确，`to_dict()` / `from_dict()` 可逆 |
| 双时间戳 | `t_ns`（软件）+ `t_hw_ns`（硬件）都是 int64 纳秒 |
| 四元数序 | `{x,y,z,w}` scalar-last，右手系（**铁律，永不静默变更**） |
| action 相对 delta | `action` 是相对前一帧的增量，非绝对位姿 |
| JSON Schema | `canonical_frame.schema.json`（Draft 2020-12），多语言可用 |
| 严格词汇 | `source.device` / `source.modality` 等枚举字段，未知值 `validate_frames` 报错 |

**铁律（§Conventions）**：
- **缺失 = 未知，禁带内哨兵**：不得用 `0` / 零向量 / `-1` / `NaN` / `""` / 标志位编码"未知/不适用"，不知道就省略该键。消费方不得给缺失可选字段填默认值。
- **LeRobot 映射 1:1**：`dotted_keys` = LeRobot 风格平面列，不做重命名或单位转换。

### 2.2 校验器

| 能力 | 验收 |
|---|---|
| `validate_frame(frame)` | 单帧校验，返回错误列表 |
| `validate_frames(iter)` | 多帧流式校验，返回 `ValidationReport` |
| `validate_frame_jsonschema(frame)` | JSON Schema 后端（可选 `jsonschema` extra） |
| `--strict-stable` | CLI flag，拒绝含 `experimental` 字段的帧（下游"只吃冻结字段"开关） |
| CI gate | exit 0/1/2（0=通过，1=有错误，2=CLI 用法错误） |

### 2.3 I/O

| 能力 | 验收 |
|---|---|
| `read_jsonl(path)` | 逐行解析 JSONL |
| `write_jsonl(frames, path)` | 显式 LF 换行（跨平台字节稳定） |
| `to_lerobot(frames)` / `from_lerobot(columns)` | 纯转置，精确 round-trip |
| `to_isaac(frames)` / `from_isaac(columns)` | 四元数序重排（scalar-last ↔ scalar-first），可选 `world_transform` 钩子 |
| `migrate_hand_v0_frames` / CLI `migrate` | 重写 Iris 存量手部数据（三个字段改名 + 丢 `hand_pose` + 补 `layout` + `frame`） |

### 2.4 Manifest

`build_manifest` / `manifest_for_episode` / `write_manifest` + CLI `manifest` 子命令。产出 `manifest.json`：`frameCount` / `episodeIndex` / `jsonlSizeBytes` / `videoPath` / `videoSizeBytes` / `durationMs`。

### 2.5 Device Adapter SDK

| 能力 | 验收 |
|---|---|
| `DeviceAdapter` ABC | `open()` / `close()` / `read_frame()` → `CanonicalFrame` |
| 迭代器协议 | `__iter__` / `__next__` |
| 上下文管理器 | `with Adapter() as a:` 自动 open/close |
| 未实现抽象方法 | 实例化时立即 `TypeError` |

### 2.6 Embodiment 登记表

`embodiments/<id>.json` + `embodiment.schema.json`。新增 `capture` 段（`default_fps` / `cameras` / `gripper_capture` / `demonstration_modes` / `calibration`）+ `capture_profiles` 命名预设。

### 2.7 骨架登记表（手部 / body）

`skeletons/<id>.json` + `skeleton.schema.json`。已注册：`mediapipe_hand_21`（stable）/ `webxr_hand_25` / `openxr_hand_26`（experimental）。`kind` 预留 `"body"`。

### 2.8 分类登记表（C12 PS0）

`taxonomies/object_class_v1.json` + `taxonomy.schema.json`。`class_id` 的唯一取值域，消费方不得自造。

### 2.9 双端语义契约（C12 / PS0）

| 对象 | 验收 |
|---|---|
| `ObservationLabel` | `label_id` / `class_id` / `confidence`（必填）/ `source` / `sensor?` / `frame_id`（仅 `map`）/ `pose` / `extent?` / `observed_at_ns`（int64 纳秒） |
| `scene_graph` | `map_id` / `revision` / `updated_at_ns` / `labels[]`（每 label = ObservationLabel + `state` / `witnesses` / `dispute?`） |
| 三个 8442 消息 | `semantic_label`（上行事件驱动）/ `scene_graph`（下行 1–5 Hz 变更驱动）/ `colocalization`（双向低频+事件） |
| 低频硬要求 | `PS_MAX_HZ` 天花板由 `validate_ps_stream` 实测校验 |
| golden 样本 | `examples/semantic/` 含 `disputed` / `stale` / `source:"headset"` 三个边界 |

---

## 3. Versioning（§Versioning）

| 变更类型 | 版本规则 |
|---|---|
| additive 字段 | **minor** |
| breaking 字段 | **major** + 迁移说明 |
| 字段级 `experimental` | 已标准化、已校验，但 stable 前可改名/改形，不算破坏性 |
| 字段级 `stable` | 冻结，仅 additive，改名需 major |
| 字段级 `deprecated` | 将移除，须附 `deprecated_since` + 迁移指引 |

**兼容性承诺**：pin `~= 0.1` 得稳定 wire 格式。
**永不静默变更的铁律**：四元数序 `{x,y,z,w}` scalar-last、右手系；`action` 相对 delta；`t_hw_ns` = pose↔video join key；dotted keys = LeRobot 风格平面列。

---

## 4. 不做什么（边界）

- 本仓**只定契约不写实现**：融合逻辑归 Daedalus（ADR-004），头显消费归 Eidolon。
- 真机操作步骤归 Parthenon `HARDWARE-OPERATIONS.md`，本仓只保留深度技术细节。
- 不长硬件驱动（Daedalus 职责）或数据平台 UI（Ambrosia 职责）。