# C12 — WebRTC 信令消息契约

> **契约编号**：C12 · **版本**：v1.0 · **状态**：生效 · **最后更新**：2026-07-27
> **上游决策**：[ROADMAP T2-comms C1](https://github.com/Mnesis-Labs/Parthenon/blob/main/ROADMAP.md) · [DECISIONS ADR](https://github.com/Mnesis-Labs/Parthenon/blob/main/DECISIONS.md)
> **消费仓**：Mnesis-Daedalus（机器人侧发送端）· Mnesis-Eidolon（Web/Quest 接收端）
> **阻塞下游**：Daedalus [`feat/webrtc-video`](https://github.com/Mnesis-Labs/Mnesis-Daedalus) · Eidolon [WebRTC 接收端](https://github.com/Mnesis-Labs/Mnesis-Eidolon)

## 声明

**本契约是对既有 v1 信封协议（`{v, type, ts, seq, session, payload}`）的 additive 增补。**
不得破坏任何现存消息定义与消费端既有行为。所有现存 conformance 用例零改动通过。

## 消息类型

本契约定义三条 WebRTC 信令消息，均在 `8442` WS 信封的 `type` 字段中标识，内容负载置于 `payload` 字段中。

### 1. `video_offer` — 消费端 → 机器人侧

**用途**：消费者（Web 前端 / Quest）发起 WebRTC 连接，向机器人侧发送 SDP Offer。

| 字段 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `stream_id` | string | 是 | 标识视频流源（如 `"camera_0"`, `"camera_panorama"`），机器人侧依据此字段选择对应的相机编码器 |
| `subscriber_id` | string | 是 | 标识该消费者实例（如 `"web_alpha"`, `"quest_main"`），用于区分同一路源的多个订阅者 |
| `sdp` | string | 是 | SDP Offer 文本（Session Description Protocol） |
| `qos_hint` | enum | 否 | 服务质量提示：`"low_latency"`（精细操作，Quest 端） 或 `"stable"`（长时建图，Web 端）。不影响编码，仅影响各订阅者的 ABR 缓冲策略 |
| `codec` | string | 否 | **预留**：V2 全景流协商时使用（如 `"H264"`, `"VP8"`, `"VP9"`）。本版始终由机器人侧编码器决定 |
| `resolution` | string | 否 | **预留**：V2 全景流协商时使用（如 `"1280x720"`, `"1920x1080"`）。本版始终由机器人侧编码器决定 |

**示例**：
```json
{
  "v": 1,
  "type": "video_offer",
  "ts": 1722096000000,
  "seq": 101,
  "session": "sess_abc123",
  "payload": {
    "stream_id": "camera_0",
    "subscriber_id": "web_alpha",
    "sdp": "v=0\r\no=- 123456 2 IN IP4 0.0.0.0\r\ns=-\r\nt=0 0\r\na=group:BUNDLE 0\r\n...",
    "qos_hint": "stable"
  }
}
```

### 2. `video_answer` — 机器人侧 → 消费端

**用途**：机器人侧响应 `video_offer`，向指定消费者返回 SDP Answer。

| 字段 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `stream_id` | string | 是 | 与 `video_offer` 中的 `stream_id` 一致，用于将该 answer 关联到正确的视频流 |
| `subscriber_id` | string | 是 | 与 `video_offer` 中的 `subscriber_id` 一致，确保应答被路由到正确的消费者 |
| `sdp` | string | 是 | SDP Answer 文本 |
| `qos_hint` | enum | 否 | 镜像 `video_offer` 中的 `qos_hint`，供消费端确认 ABR 策略 |

**示例**：
```json
{
  "v": 1,
  "type": "video_answer",
  "ts": 1722096000050,
  "seq": 201,
  "session": "sess_abc123",
  "payload": {
    "stream_id": "camera_0",
    "subscriber_id": "web_alpha",
    "sdp": "v=0\r\no=- 654321 2 IN IP4 192.168.1.100\r\ns=-\r\nt=0 0\r\na=group:BUNDLE 0\r\n...",
    "qos_hint": "stable"
  }
}
```

### 3. `video_ice` — 双向

**用途**：WebRTC ICE Candidate 交换（双方均可发送）。

| 字段 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `stream_id` | string | 是 | 标识该 candidate 所属的视频流 |
| `subscriber_id` | string | 是 | 标识该 candidate 所属的消费者 |
| `candidate` | string | 是 | ICE candidate 字符串（如 `"candidate:1 1 UDP 2122252543 192.168.1.100 5000 typ host"`） |
| `sdp_mid` | string | 否 | SDP media stream identification（如 `"0"`），用于 candidate 与媒体流的关联 |
| `sdp_mline_index` | integer | 否 | SDP media line 索引（从 0 开始），用于 candidate 与媒体流的关联 |

**示例**：
```json
{
  "v": 1,
  "type": "video_ice",
  "ts": 1722096000100,
  "seq": 301,
  "session": "sess_abc123",
  "payload": {
    "stream_id": "camera_0",
    "subscriber_id": "web_alpha",
    "candidate": "candidate:1 1 UDP 2122252543 192.168.1.100 5000 typ host",
    "sdp_mid": "0",
    "sdp_mline_index": 0
  }
}
```

## 设计要点

### 多订阅者模型

**多订阅者是常态，不是例外。** 同一路视频源（`stream_id`）可被多个独立消费者（`subscriber_id`）各自协商 WebRTC 连接。每对 `(stream_id, subscriber_id)` 构成一个独立的信令会话。

典型案例：
- `stream_id="camera_0"` 同时被 `subscriber_id="web_alpha"`（Web 端建图）和 `subscriber_id="quest_main"`（Quest 端精细操作）订阅
- 双方各自独立完成 `video_offer` ↔ `video_answer` ↔ `video_ice` 信令握手
- 机器人侧为每个 `subscriber_id` 维护独立的 PeerConnection

### QoS 提示与编码策略

`qos_hint` 是对同一个编码流的各订阅者 ABR 缓冲策略提示，**不分裂编码**：
- `low_latency`：低延迟缓冲（适合 Quest 精细操作，≤80ms 端到端）
- `stable`：稳定长时缓冲（适合 Web 建图 / 3DGS 采集，容忍略高延迟）

### V2 全景流预留

`codec` 和 `resolution` 字段为 V2 阶段 360° 全景流做预留。本版（v1）始终由机器人侧编码器决定编码参数，不对这两个字段做校验。

## 消费端升版路径

### Mnesis-Daedalus（机器人侧）

1. 在 `xr_bridge` 的 WS 消息路由中注册 `video_offer` 和 `video_ice`（接收）以及 `video_answer` 和 `video_ice`（发送）的消息类型
2. 根据 `stream_id` 选择对应的相机编码器
3. 为每个 `(stream_id, subscriber_id)` 对维护独立的 PeerConnection 实例
4. 根据 `qos_hint` 调整 ABR 缓冲参数（可选）
5. **contracts.lock 摘录**：本契约 sha256 摘要应纳入 `contracts.lock` 校验体系

### Mnesis-Eidolon（消费端）

1. 在 WebSocket 客户端中注册 `video_answer` 和 `video_ice`（接收）以及 `video_offer` 和 `video_ice`（发送）的消息类型
2. 为每个 `(stream_id, subscriber_id)` 对维护独立的 PeerConnection 实例
3. `qos_hint` 默认值：Web 端优先 `"stable"`，Quest 端优先 `"low_latency"`
4. 在不支持 `qos_hint` 的旧版本中，忽略该字段（`qos_hint` 为可选字段）

## 兼容性

- 本契约所有消息均为 **additive**：新增 `type` 值，不修改任何现有消息的 schema
- 消费端如遇到不认识的消息类型，应忽略（遵循 WS 信封协议已有的未知消息处理规则）
- `qos_hint`、`codec`、`resolution` 为可选字段，消费端可安全忽略
- 缺少 `stream_id` 或 `subscriber_id` 的消息应被拒绝

## 变更记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-07-27 | v1.0 | 初始发布 |
| 2026-07-28 | v1.1 | 纳入 SPEC.md §8 Conventions 铁律：缺失 = 未知，禁止带内哨兵。所有可选字段（`qos_hint`、`codec`、`resolution`）缺失即视为"该信息不可用"，消费方不得填入默认值（参见 [SPEC.md §8.1](../SPEC.md#81-铁律缺失--未知禁止带内哨兵)）。 |

---

## 编号说明（2026-07-28 抢救归位时补）

本契约在 ROADMAP `T2-comms` 里被称作 **C1**，那是**路线图轨道内的序号**；本仓
`CONTRACTS.md` 跨仓契约登记簿的 `C1` 已被 **Canonical Frame Schema** 占用，`C2`–`C11`
同样已分配（含草案）。为免撞号，登记簿内按下一个空号 **C12** 登记，正文标题随之统一。
两处指同一份契约，引用时以本文件路径为准。
