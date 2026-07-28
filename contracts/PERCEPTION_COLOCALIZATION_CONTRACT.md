# C13 — 双端感知与共定位消息契约（PS 轨）

> **契约编号**：C13 · **版本**：v1.1 · **状态**：生效 · **最后更新**：2026-07-28
> **上游决策**：Parthenon [#58](https://github.com/Mnesis-Labs/Parthenon/pull/58) · Daedalus [ADR-004](https://github.com/Mnesis-Labs/Mnesis-Daedalus/pull/238) · [SPEC.md](../SPEC.md)（本仓 PS 轨规格 SSOT）
> **消费仓**：Mnesis-Daedalus（机器人侧感知 + 融合）· Mnesis-Eidolon（头显侧消费 + 标注上报）
> **阻塞下游**：Daedalus PS1/PS2a/PS3 · Eidolon PS2b/PS4

## 声明

**本契约是对既有 v1 信封协议（`{v, type, ts, seq, session, payload}`）的 additive 增补。**
不得破坏任何现存消息定义与消费端既有行为。所有现存 conformance 用例零改动通过。

## 共享类型

### ObservationLabel

统一观测标签，由机器人端或头显端产出。

**Schema**：[`schema/observation_label.json`](../schema/observation_label.json)

| 字段 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `label_id` | string (uuid) | 是 | 稳定 id，跨帧跟踪 |
| `class_id` | string | 是 | 取自 `taxonomies/class_ids.json` 的类别标识，两端不得自造 |
| `confidence` | number [0, 1] | 是 | 置信度 |
| `source` | enum | 是 | 产出端：`robot` / `headset` / `human` |
| `sensor` | string | 是 | 传感器标识 |
| `frame_id` | string | 是 | 参考坐标系，必须是共同参考系（如 `map`），不接受局部系 |
| `pose` | object | 是 | 6-DoF 位姿：`{ t: [x,y,z], q: [x,y,z,w] }` |
| `extent` | array [3] | 否 | 3D bbox 尺寸 `[dx, dy, dz]`，可空 |
| `observed_at` | number | 是 | 观测时间戳（Unix 秒，支持小数） |

**示例**：
```json
{
  "label_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "class_id": "cup",
  "confidence": 0.87,
  "source": "robot",
  "sensor": "cam_overhead",
  "frame_id": "map",
  "pose": { "t": [0.5, -0.3, 0.8], "q": [0.0, 0.0, 0.0, 1.0] },
  "extent": [0.08, 0.08, 0.12],
  "observed_at": 1753660800.123
}
```

### SceneGraph

融合后的语义地图，由机器人端权威产出。

**Schema**：[`schema/scene_graph.json`](../schema/scene_graph.json)

| 字段 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `map_id` | string | 是 | 语义地图标识 |
| `revision` | integer | 是 | 单调递增修订号，消费端据此判断是否需要重绘 |
| `updated_at` | number | 是 | 更新时间戳 |
| `labels` | array | 是 | 语义标签列表 |

标签除 ObservationLabel 字段外，附加：

| 字段 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `state` | enum | 是 | 标签状态：`confirmed` / `unconfirmed` / `disputed` / `stale` |
| `witnesses` | array[enum] | 是 | 见证该标签的端点列表 |
| `dispute` | object | 争议时必需 | 争议详情，仅 `state=disputed` 时存在 |

## 消息类型

本契约定义三条消息，均在 `8442` WS 信封的 `type` 字段中标识，内容负载置于 `payload` 字段中。

### 1. `semantic_label` — 上行（头显→桥）

**用途**：头显侧标注/识别结果，上报至桥接层。

| 属性 | 值 |
|------|------|
| 方向 | 上行（头显→桥） |
| 频率 | 事件驱动 |
| payload schema | [`schema/semantic_label.json`](../schema/semantic_label.json) |

payload 即为一个完整的 ObservationLabel。

**示例**：
```json
{
  "v": 1,
  "type": "semantic_label",
  "ts": 1753660800123,
  "seq": 1,
  "session": "sess_abc123",
  "payload": {
    "label_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "class_id": "cup",
    "confidence": 0.87,
    "source": "headset",
    "sensor": "cam_passthrough",
    "frame_id": "map",
    "pose": { "t": [0.5, -0.3, 0.8], "q": [0.0, 0.0, 0.0, 1.0] },
    "observed_at": 1753660800.123
  }
}
```

### 2. `scene_graph` — 下行（桥→头显）

**用途**：融合后的语义地图，下发给头显端消费。

| 属性 | 值 |
|------|------|
| 方向 | 下行（桥→头显） |
| 频率 | **1–5 Hz，变更驱动** |
| 说明 | 融合后的语义地图 |
| payload schema | [`schema/scene_graph.json`](../schema/scene_graph.json) |

**约束**：`revision` 单调递增，消费端据此判断是否需要重绘。1–5 Hz 变更驱动，**不得与 30 Hz teleop frame 抢带宽**。

### 3. `colocalization` — 双向

**用途**：头显在共同参考系下的外参、质量指标、事件。

| 属性 | 值 |
|------|------|
| 方向 | 双向 |
| 频率 | 低频 + 事件 |
| payload schema | [`schema/colocalization.json`](../schema/colocalization.json) |

| 字段 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `T_map_headset` | object | 是 | 头显在 map 系下的外参 `{ t: [x,y,z], q: [x,y,z,w] }` |
| `quality` | number [0, 1] | 是 | 共定位质量指标 |
| `event` | string \| null | 是 | `null`（常规更新）或 `"colocalization_stale"`（共定位过期事件） |

## 设计要点

### source 枚举第一天含 headset

即使头显侧识别（PS4）是 backlog，`source` 枚举值从第一天就包含 `"headset"`。后期补上时**不改契约**。同理 `"human"`（人裁决产生的标签）。

### class_id 取值域

`class_id` 必须来自本仓 `taxonomies/class_ids.json`，消费方（Daedalus、Eidolon）不得自造。新类别通过规范流程（PR 到本仓 `taxonomies/`）扩展。

### 低频硬要求

`scene_graph` 1–5 Hz 变更驱动，`colocalization` 低频 + 事件驱动，**不得与 30 Hz teleop frame 抢带宽**。桥接层应实现带宽门控，确保感知消息不影响遥操作实时性。

### frame_id 必须是共同参考系

所有位姿（ObservationLabel.pose、SceneGraph.labels[].pose、Colocalization.T_map_headset）都必须在共同参考系（如 `map`）下表达。消费端不接受局部参考系，融合器不负责坐标系变换。

## 消费端升版路径

### Mnesis-Daedalus（机器人侧）

1. 在 `xr_bridge` 的 WS 消息路由中注册 `semantic_label`（接收）和 `scene_graph` + `colocalization`（发送）的消息类型
2. 实现 PS1 感知管线（推理 + 坐标变换到 map 系）
3. 实现 PS2a 融合器（标签对齐 + 争议裁决），由 ADR-004 定义
4. 实现 scene_graph 变更驱动下发（1–5 Hz）
5. 将 `colocalization` 消息路由到共定位模块
6. **contracts.lock 摘录**：本契约 sha256 摘要应纳入 `contracts.lock` 校验体系

### Mnesis-Eidolon（头显侧）

1. 在 WebSocket 客户端中注册 `semantic_label`（发送）和 `scene_graph` + `colocalization`（接收）的消息类型
2. 根据 `scene_graph.revision` 判断是否需要重绘语义图层
3. 发送 `semantic_label` 时确保 `source` 为 `"headset"`，`frame_id` 为 `"map"`
4. 消费 `colocalization` 消息更新头显在 map 系下的位姿
5. 在不支持 `colocalization` 的旧版本中，忽略该消息类型

## 兼容性

- 本契约所有消息均为 **additive**：新增 `type` 值，不修改任何现有消息的 schema
- 消费端如遇到不认识的消息类型，应忽略（遵循 WS 信封协议已有的未知消息处理规则）
- `extent` 为可选字段，消费端可安全忽略
- 缺少必需字段的 payload 应被拒绝

## 变更记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-07-28 | v1.1 | 纳入 SPEC.md §8 Conventions 铁律「缺失 = 未知，禁止带内哨兵」+ §8.2 字段级 status 定义。所有现有字段标记为 `stable`。参见 [SPEC.md](../SPEC.md) §8、§9。 |

---

---

## 编号说明（2026-07-28 抢救归位时补）

本契约在 PS 轨设计文档里被称作 **C2**，那是**轨道内序号**；本仓 `CONTRACTS.md`
跨仓契约登记簿的 `C2` 已被 **Episodes Ingest HTTP** 占用，`C1`–`C11` 同样已分配
（含草案）。为免撞号，登记簿内按空号 **C13** 登记（`C12` 为同批归位的 WebRTC 信令
契约），正文标题随之统一。两处指同一份契约，引用时以本文件路径为准。
