# XR_ROBOT_CONTRACT — xr_bridge WebSocket 实时遥操作契约

> **契约编号**: C3
> **版本**: v1.4
> **Owner（定义方）**: Daedalus（`docs/integration/XR_ROBOT_CONTRACT.md` 镜像于此）
> **消费方**: Eidolon（Quest VR 前端）
> **两侧测试**: Daedalus harness + 坐标真值 fixture · Eidolon PH-2/PH-3 测试
> **权威位置**: 本文件（`contracts/XR_ROBOT_CONTRACT.md`）为单一真值；各仓副本为只读镜像。

---

## 1. 概述

xr_bridge 是 Mnesis 系统中 VR 前端（Quest / Eidolon）与机器人执行端（Daedalus）之间的**实时双向 WebSocket 通信桥梁**，用于：

- 从 VR 端向机器人端发送**遥操作指令**（末端位姿/关节角/使能/急停）
- 从机器人端向 VR 端回传**状态反馈**（关节读数/执行状态/异常/被控端信息）
- 双向**急停闩锁**（E-Stop latch）
- **重连再锚定**（断线后恢复双向状态一致性）
- **看门狗**（心跳超时 → 自动安全停止）

---

## 2. 协议基础

### 2.1 传输层

| 属性 | 值 |
|---|---|
| 协议 | WebSocket (WSS) |
| 端点模式 | VR 端主动连接机器人端 WebSocket 服务 |
| URL 模板 | `ws://<robot_host>:<port>/xr_bridge` |
| 安全 | 内网使用（物理隔离），不设加密认证；未来外网场景加 Token |

### 2.2 消息格式

所有消息为 **JSON 文本帧**，UTF-8 编码，单帧包含：

```json
{
  "type": "<message_type>",
  "seq": <uint32>,
  "ts": <int64>,
  "body": { ... }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | string | 消息类型（见 §3） |
| `seq` | uint32 | 发送方单调递增序列号（双边独立） |
| `ts` | int64 | 发送方 Unix 纳秒时间戳 (`System.nanoTime` base) |
| `body` | object | 消息载荷（类型相关） |

### 2.3 连接生命周期

```
VR ─── WS Connect ──→ Robot          [建立连接]
VR ←── C3_Info ───── Robot           [机器人端发送自身规格]
VR ─── C3_Bind ────→ Robot           [VR 端选择被控臂]
VR ←── C3_Bound ──── Robot           [绑定确认 + 初始状态]
VR ─── C3_Frame ──→ Robot            [遥操作帧循环]
VR ←── C3_Status ─── Robot           [状态回传循环]
  ... (heartbeat continues) ...
VR ─── C3_EStop ──→ Robot            [任一方向急停]
  or  Robot ─── C3_EStop ──→ VR
  ... (watchdog timeout → auto-stop) ...
VR ─── WS Close ──── Robot           [正常断开]
```

---

## 3. 消息类型

### 3.1 `C3_Info` — 机器 -> VR（连接建立后立即发送）

机器人端向 VR 通告自身能力。

**body**:
```json
{
  "robot_name": "SO-ARM101",
  "arms": [
    {"name": "main", "dof": 7, "joint_names": ["j1",...,"j7"]}
  ],
  "protocol_version": "1.4",
  "can_estop": true,
  "watchdog_timeout_ms": 500
}
```

### 3.2 `C3_Bind` — VR -> 机器（选择被控臂）

```json
{
  "arm": "main"
}
```

### 3.3 `C3_Bound` — 机器 -> VR（绑定确认）

```json
{
  "arm": "main",
  "initial_joint_positions": [0.0, 0.0, 0.0, ..., 0.0],
  "initial_pose_SE3": [tx, ty, tz, qx, qy, qz, qw]
}
```

### 3.4 `C3_Frame` — VR -> 机器（遥操作控制帧，循环发送）

高频控制帧（典型速率 60–90 Hz，匹配 VR 头显刷新率）。

```json
{
  "target_pose_SE3": [tx, ty, tz, qx, qy, qz, qw],
  "gripper": 0.0,
  "mode": "position"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `target_pose_SE3` | float[7] | 末端目标位姿（米 + 四元数 {x,y,z,w}） |
| `gripper` | float | 夹爪开度 [0.0, 1.0] |
| `mode` | string | `"position"`（位姿控制）或 `"joint"`（关节控制，预留） |

### 3.5 `C3_Status` — 机器 -> VR（状态回传，循环发送）

反馈帧与 `C3_Frame` 异步交错，典型速率 30–60 Hz。

```json
{
  "joint_positions": [0.0, ..., 0.0],
  "joint_velocities": [0.0, ..., 0.0],
  "pose_SE3": [tx, ty, tz, qx, qy, qz, qw],
  "gripper": 0.0,
  "executing": true,
  "error": null
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `joint_positions` | float[N] | 各关节当前角度（rad） |
| `joint_velocities` | float[N] | 各关节当前速度（rad/s） |
| `pose_SE3` | float[7] | 末端当前位姿（米 + 四元数） |
| `gripper` | float | 夹爪当前开度 |
| `executing` | bool | 当前运动指令是否执行中 |
| `error` | string\|null | 错误信息（非空时表示异常） |

### 3.6 `C3_EStop` — 双向（任一方向触发即急停）

紧急停止消息——本消息不可重试，接收方应立即物理停止。

```json
{
  "reason": "operator_triggered",
  "source": "vr"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `reason` | string | 急停原因枚举 |
| `source` | string | `"vr"` 或 `"robot"` |

急停后系统进入闩锁状态：必须通过**软重置消息**或**重新连接**才能恢复运动。

**急停原因枚举**:
- `"operator_triggered"` — 操作员手动触发
- `"watchdog_timeout"` — 看门狗超时
- `"joint_limit_exceeded"` — 关节超限
- `"communication_loss"` — 通信丢失
- `"internal_error"` — 内部错误

### 3.7 `C3_Heartbeat` — 双向（周期性心跳）

```json
{
  "counter": <uint32>
}
```

看门狗：双方在收到对方心跳后重置本地看门狗计时器。超时（`watchdog_timeout_ms` 内未收到任何消息）则自动触发 `C3_EStop`。

### 3.8 `C3_Reset` — VR -> 机器（急停后恢复）

```json
{
  "ack": true
}
```

此消息仅在急停闩锁状态下有效。机器收到后应清除闩锁，回 home 位，然后发送 `C3_Bound` 重新锚定。

---

## 4. 急停闩锁（E-Stop Latch）

- 急停是**上升沿触发**的闩锁：一旦触发，即使发送方恢复，接收方也不自动解除。
- 闩锁状态独立于 WebSocket 连接状态：断线重连后，两端应重新协商闩锁状态。
- 解除闩锁的唯一途径：`C3_Reset` 消息 + 机器人端安全确认 → 重新锚定。

---

## 5. 重连再锚定（Reconnect Re-Anchor）

断线重连流程：

1. VR 端检测到 WebSocket 断开（`onclose` / 看门狗超时）
2. VR 端周期性尝试重连（指数退避：100ms → 500ms → 2s → 5s cap）
3. 重连成功后，机器发送 `C3_Info`
4. VR 发送 `C3_Bind` 重新选择被控臂（可能不同）
5. 机器发送 `C3_Bound`（含当前真实位姿）
6. VR 以此位姿重新锚定自身控制映射，恢复正常控制循环

**关键要求**：重连后的 `C3_Bound` 位姿代表机器人当前实际物理状态——VR 端不得假设断线前的位姿仍然有效。

---

## 6. 看门狗（Watchdog）

| 参数 | 默认值 | 说明 |
|---|---|---|
| `watchdog_timeout_ms` | 500 | 毫秒，由机器在 `C3_Info` 中宣告 |
| 心跳间隔 | 100 ms | 双方每 100ms 发送一次 `C3_Heartbeat` |

- 任何收到的消息都重置看门狗计时器（不仅限于 `C3_Heartbeat`——`C3_Frame` / `C3_Status` 同样有效）
- 超时 → 自动触发 `C3_EStop`（reason=`"watchdog_timeout"`）

---

## 7. 坐标约定

| 约定 | 值 |
|---|---|
| 坐标系 | 右手系，Y-up |
| 位置单位 | 米（SI） |
| 旋转表示 | 四元数 {x, y, z, w}（标量最后） |
| 末端位姿 | 基座坐标系下的末端执行器位姿 |
| VR 映射 | VR 手柄位姿 → 机器人末端位姿，映射矩阵在重连锚定时锁定 |

---

## 8. 安全规则

1. **急停优先**：任何检测到异常的一方应立即发送 `C3_EStop`，不应等待确认。
2. **速度限制**：机器人端应实现末端速度软限（默认 ≤ 2 m/s）。
3. **关节限位**：机器人端应拒绝超出物理关节限位的指令（通过 `C3_Status.error` 报告）。
4. **断线保护**：WebSocket 断开后机器人端应自动停止运动（硬件看门狗落地）。
5. **日志**：所有 `C3_EStop` 事件必须写入持久化日志（两侧各自记录）。

---

## 9. 版本历史

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 | — | 初始版 |
| v1.1 | — | 增加 `C3_Heartbeat` + 看门狗机制 |
| v1.2 | — | 增加 `C3_EStop` 闩锁语义 + 断线保护 |
| v1.3 | — | 增加重连再锚定流程（§5） |
| v1.4 | 2026-07 | 当前版本。增加 `C3_Reset` 消息；明确坐标约定（§7）；细化安全规则（§8）。本文件迁入 canonical 作为单一真值。 |
