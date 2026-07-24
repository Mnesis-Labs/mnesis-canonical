# XR_ROBOT_CONTRACT — xr_bridge WebSocket 实时遥操作契约

> **契约编号**: C3
> **版本**: v1.5
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
- **规划预览与确认执行**（ghost trajectory / plan gate / execute confirm）

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

**双臂数组信封**：`C3_Frame` 和 `C3_Status` 的 body 使用 `arms[]` 数组承载多臂数据。单臂端发送 1 元素数组，向后兼容 v1.2。`arms[]` 中每个元素通过 `arm_id` 区分。

```json
{
  "type": "C3_Frame",
  "seq": 42,
  "ts": 1712345678000000000,
  "body": {
    "arms": [
      {"arm_id": "left",  "target_pose_SE3": [0.3, 0.0, 0.8, 0.0, 0.0, 0.0, 1.0], "gripper": 0.4, "clutch": true},
      {"arm_id": "right", "target_pose_SE3": [0.3, -0.4, 0.8, 0.0, 0.0, 0.0, 1.0], "gripper": 0.0, "clutch": false}
    ]
  }
}
```

### 2.3 连接生命周期

```
VR ─── WS Connect ──→ Robot          [建立连接]
VR ←── C3_Info ───── Robot           [机器人端发送自身规格]
VR ─── C3_Bind ────→ Robot           [VR 端选择被控臂]
VR ←── C3_Bound ──── Robot           [绑定确认 + 初始状态]
VR ─── C3_Frame ──→ Robot            [遥操作帧循环]
VR ←── C3_Status ─── Robot           [状态回传循环]
  ... (heartbeat continues) ...
  ... (plan preview flow) ...
VR ←── C3_GhostTrajectory ── Robot   [规划预览轨迹]
VR ←── C3_PlanStatus ─────── Robot   [规划状态]
VR ─── C3_ExecuteConfirm ──→ Robot   [确认执行]
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
  "protocol_version": "1.5",
  "can_estop": true,
  "watchdog_timeout_ms": 500
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `robot_name` | string | 机器人型号标识 |
| `arms` | array | 可用臂列表 |
| `arms[].name` | string | 臂标识（如 `"main"` / `"left"` / `"right"`） |
| `arms[].dof` | uint | 自由度 |
| `arms[].joint_names` | string[] | 关节名称列表 |
| `protocol_version` | string | 协议版本号 |
| `can_estop` | bool | 是否支持急停 |
| `watchdog_timeout_ms` | uint | 看门狗超时毫秒数 |

### 3.2 `C3_Bind` — VR -> 机器（选择被控臂）

```json
{
  "arm": "main"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `arm` | string | 被控臂标识（对应 `C3_Info.arms[].name`） |

### 3.3 `C3_Bound` — 机器 -> VR（绑定确认）

```json
{
  "arm": "main",
  "initial_joint_positions": [0.0, 0.0, 0.0, ..., 0.0],
  "initial_pose_SE3": [tx, ty, tz, qx, qy, qz, qw]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `arm` | string | 已绑定臂标识 |
| `initial_joint_positions` | float[N] | 各关节当前角度（rad） |
| `initial_pose_SE3` | float[7] | 末端当前位姿（米 + 四元数） |

### 3.4 `C3_Frame` — VR -> 机器（遥操作控制帧，循环发送）

高频控制帧（典型速率 60–90 Hz，匹配 VR 头显刷新率）。使用 **arms[] 数组信封** 支持多臂。

```json
{
  "arms": [
    {
      "arm_id": "main",
      "target_pose_SE3": [tx, ty, tz, qx, qy, qz, qw],
      "gripper": 0.0,
      "clutch": false
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `arms` | array | **双臂数组信封**。单臂端发送 1 元素数组，向后兼容 v1.2 |
| `arms[].arm_id` | string | 臂标识（对应 `C3_Info.arms[].name`） |
| `arms[].target_pose_SE3` | float[7] | 末端目标位姿（米 + 四元数 {x,y,z,w}） |
| `arms[].gripper` | float | 夹爪**闭合程度** [0.0, 1.0]：`0.0` = 完全张开，`1.0` = 完全闭合（方向与 canonical `action.gripper` / `observation.gripper` 一致） |
| `arms[].clutch` | bool | clutch 脱开状态：true = 脱开（不跟随指令，末端保持当前位姿） |
| `arms[].mode` | string | 可选，`"position"`（默认）或 `"joint"`（预留）；对应 ≤v1.4 的顶层 `mode` 字段 |

> **`gripper` 端点定义（消费方核对提示）**：`arms[].gripper` 采**闭合程度**语义，`0.0` = 完全张开、`1.0` = 完全闭合，方向与 canonical `action.gripper` / `observation.gripper` 一致。此定义明确前既有实现（Daedalus xr_bridge / Eidolon / airbot webapp）可能按相反方向理解，接入前须各自核对对齐（各仓核对属后续独立卡）。此为把既有模糊补明确，**wire 版本不变（仍 v1.5）**。

### 3.5 `C3_Status` — 机器 -> VR（状态回传，循环发送）

反馈帧与 `C3_Frame` 异步交错，典型速率 30–60 Hz。使用 **arms[] 数组信封** 支持多臂。

```json
{
  "arms": [
    {
      "arm_id": "main",
      "joint_positions": [0.0, ..., 0.0],
      "joint_velocities": [0.0, ..., 0.0],
      "eef_pose": [tx, ty, tz, qx, qy, qz, qw],
      "gripper": 0.0,
      "health": "ok"
    }
  ],
  "executing": true,
  "error": null
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `arms` | array | **双臂数组信封**。单臂端发送 1 元素数组，向后兼容 v1.2 |
| `arms[].arm_id` | string | 臂标识 |
| `arms[].joint_positions` | float[N] | 各关节当前角度（rad） |
| `arms[].joint_velocities` | float[N] | 各关节当前速度（rad/s） |
| `arms[].eef_pose` | float[7] | 末端当前位姿（米 + 四元数） |
| `arms[].gripper` | float | 夹爪当前**闭合程度** [0.0, 1.0]：`0.0` = 完全张开，`1.0` = 完全闭合（同 `C3_Frame.arms[].gripper` 方向） |
| `arms[].health` | string | 臂级健康状态：`ok` / `warning` / `error` |
| `executing` | bool | 全局执行状态（任一臂执行中即为 true） |
| `error` | string\|null | 全局错误信息 |

### 3.6 `C3_EStop` — 双向（任一方向触发即急停）

紧急停止消息——本消息不可重试，接收方应立即物理停止。

```json
{
  "reason": "operator_triggered",
  "source": "vr",
  "arm_id": null
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `reason` | string | 急停原因枚举 |
| `source` | string | `"vr"` 或 `"robot"` |
| `arm_id` | string\|null | **诊断字段**：标注触发来源臂（如某臂 watchdog 超时）；`null` = 非臂级来源。**无论 arm_id 取值，急停一律全局——所有臂立即停止**（安全铁律：绝不允许单臂急停，见 §8-2） |

急停后系统进入闩锁状态：必须通过**软重置消息**或**重新连接**才能恢复运动。

**急停原因枚举**:
- `"operator_triggered"` — 操作员手动触发
- `"watchdog_timeout"` — 看门狗超时（arm_id 标注超时臂）
- `"joint_limit_exceeded"` — 关节超限（arm_id 标注超限臂）
- `"communication_loss"` — 通信丢失
- `"internal_error"` — 内部错误

> 所有 reason 触发的急停均为**全局**；arm_id 仅用于诊断定位。

### 3.7 `C3_Heartbeat` — 双向（周期性心跳）

```json
{
  "counter": <uint32>
}
```

看门狗：双方在收到对方心跳后重置本地看门狗计时器。超时（`watchdog_timeout_ms` 内未收到任何消息）则自动触发 `C3_EStop`。

**逐臂看门狗（检测逐臂、停止全局）**：在多臂模式下，每臂独立维护看门狗计时器（检测粒度逐臂）。若某臂的 `C3_Frame` 或 `C3_Status` 在超时阈值内未收到，则触发 `C3_EStop`（`arm_id` 标注超时臂）——**急停动作为全局，所有臂同时进入闩锁**。全局心跳（`C3_Heartbeat`）重置所有臂的看门狗计时器。

### 3.8 `C3_Reset` — VR -> 机器（急停后恢复）

```json
{
  "ack": true
}
```

此消息仅在急停闩锁状态下有效。机器收到后应清除闩锁，回 home 位，然后发送 `C3_Bound` 重新锚定。

### 3.9 `C3_GhostTrajectory` — 机器 -> VR（规划预览轨迹）

当机器端规划完成一次轨迹后，向 VR 端推送降采样的轨迹预览，供操作员审看。

```json
{
  "arm_id": "main",
  "goal_seq": 7,
  "joint_waypoints": [[0.0, 0.1, ...], [0.2, 0.15, ...], ...],
  "eef_waypoints": [[0.3, 0.0, 0.8, 0.0, 0.0, 0.0, 1.0], ...],
  "duration_ms": 3200
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `arm_id` | string | 目标臂标识 |
| `goal_seq` | uint32 | 规划目标序列号（与 `C3_PlanStatus` / `C3_ExecuteConfirm` 联动） |
| `joint_waypoints` | float[N][] | 降采样关节轨迹点序列（每点 = float[N] 关节角度） |
| `eef_waypoints` | float[7][] | 末端轨迹点序列（每点 = 位姿 [tx,ty,tz, qx,qy,qz,qw]） |
| `duration_ms` | uint32 | 轨迹预计执行时长（毫秒） |

### 3.10 `C3_PlanStatus` — 机器 -> VR（规划状态变更）

机器端规划状态变更时主动推送，驱动 VR 端幽灵预览配色与 UX。

```json
{
  "arm_id": "main",
  "goal_seq": 7,
  "status": "ok",
  "message": "目标可达，预计 3.2s 执行"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `arm_id` | string | 目标臂标识 |
| `goal_seq` | uint32 | 规划目标序列号 |
| `status` | string | 规划状态枚举 |
| `message` | string\|null | 可读说明（可选） |

**规划状态枚举**:
- `"planning"` — 规划进行中
- `"ok"` — 目标可达，轨迹已生成
- `"unreachable"` — IK 不可达
- `"collision"` — 规划路径存在碰撞（自碰/环境碰撞）
- `"expired"` — 预览有效期（30s）已过，需重新规划

### 3.11 `C3_ExecuteConfirm` — VR -> 机器（确认执行）

操作员在 VR 端审看幽灵轨迹后，确认执行的指令。

```json
{
  "arm_id": "main",
  "goal_seq": 7
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `arm_id` | string | 目标臂标识 |
| `goal_seq` | uint32 | 确认执行的规划目标序列号。机器端 PlanGate 校验：若 `goal_seq` 已过期或不匹配当前预览，则拒绝执行，返回 `C3_PlanStatus {status: "expired"}` |

---

## 4. 急停闩锁（E-Stop Latch）

- 急停是**上升沿触发**的闩锁：一旦触发，即使发送方恢复，接收方也不自动解除。
- 闩锁状态独立于 WebSocket 连接状态：断线重连后，两端应重新协商闩锁状态。
- 解除闩锁的唯一途径：`C3_Reset` 消息 + 机器人端安全确认 → 重新锚定。
- **全局闩锁（唯一语义）**：任何 `C3_EStop`（无论 `arm_id`/`reason` 取值）都使**所有臂**进入闩锁状态。`arm_id` 仅用于诊断（定位触发来源臂），不改变闩锁范围。双臂必须同停，**绝不允许单臂急停**（安全铁律，来源 Parthenon research/17 §2.2）。

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
- **逐臂看门狗（检测逐臂、停止全局）**：多臂模式下每臂独立维护看门狗计时器；某臂的 `C3_Frame` 或 `C3_Status` 超时即触发 `C3_EStop`（arm_id 标注超时臂）——**所有臂全部停止并闩锁**。
- 全局 `C3_Heartbeat` 重置所有臂的看门狗计时器。
- 超时 → 自动触发 `C3_EStop`（reason=`"watchdog_timeout"`，arm_id 对应超时臂，连接级超时 arm_id=`null`；停止范围一律全局）

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
2. **急停一律全局**：任何来源（操作员/看门狗/关节超限/内部错误）触发的 `C3_EStop` 都使所有臂立即停止并闩锁。**绝不允许单臂急停**——双臂协同场景下另一臂继续运动是不可接受的安全风险。`arm_id` 仅作诊断标注。
3. **看门狗检测逐臂**：多臂模式下超时检测按臂独立计时（提高检测灵敏度），但触发的停止动作全局。
4. **速度限制**：机器人端应实现末端速度软限（默认 ≤ 2 m/s）。
5. **关节限位**：机器人端应拒绝超出物理关节限位的指令（通过 `C3_Status.arms[].health` 和 `C3_Status.error` 报告）。
6. **PlanGate 安全**：未经过 `C3_PlanStatus {status: "ok"}` 的轨迹，机器人端不得执行。`C3_ExecuteConfirm` 中的 `goal_seq` 必须匹配当前有效预览。
7. **规划预览有效期**：`C3_PlanStatus {status: "ok"}` 后 30 秒内未收到 `C3_ExecuteConfirm`，状态自动变为 `"expired"`，需重新规划。
8. **断线保护**：WebSocket 断开后机器人端应自动停止所有臂的运动（硬件看门狗落地）。
9. **日志**：所有 `C3_EStop` 事件必须写入持久化日志（两侧各自记录）。

---

## 9. 向后兼容性

- v1.2/v1.3/v1.4 客户端可忽略 `C3_GhostTrajectory`、`C3_PlanStatus`、`C3_ExecuteConfirm` 消息，不影响遥操作核心功能。
- **接收端义务（wire format 零破坏的关键）**：v1.5 服务端 **MUST** 兼容接收 ≤v1.4 的平铺 `C3_Frame` body（顶层 `target_pose_SE3`/`gripper`/`mode`，无 `arms[]`），并等价视为 `arms: [{"arm_id": "main", "target_pose_SE3": ..., "gripper": ..., "clutch": false}]`；对 ≤v1.4 客户端回发 `C3_Status` 时按 `C3_Info.protocol_version` 协商降级为平铺格式。
- 单臂 v1.5 端发送 `C3_Frame` 时使用 `arms: [{arm_id: "main", ...}]` 1 元素数组。
- `mode` 字段（`"position"` / `"joint"`，≤v1.4 顶层字段）保留为 `arms[]` 元素的**可选**字段，缺省 `"position"`。
- 新增字段均为可选/扩展，不破坏现有消息结构。

---

## 10. 版本历史

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 | — | 初始版 |
| v1.1 | — | 增加 `C3_Heartbeat` + 看门狗机制 |
| v1.2 | — | 增加 `C3_EStop` 闩锁语义 + 断线保护 |
| v1.3 | — | 增加重连再锚定流程（§5） |
| v1.4 | 2026-07 | 增加 `C3_Reset` 消息；明确坐标约定（§7）；细化安全规则（§8）。本文件迁入 canonical 作为单一真值 |
| v1.5 | 2026-07 | **双臂数组信封**：`C3_Frame` 和 `C3_Status` 使用 `arms[]` 数组支持多臂，单臂端发送 1 元素数组向后兼容。**新增三消息**：`C3_GhostTrajectory`（规划预览轨迹）、`C3_PlanStatus`（规划状态变更）、`C3_ExecuteConfirm`（确认执行）。**逐臂 watchdog + 全局 estop 语义**：watchdog 逐臂独立超时检测；estop 一律全局停止，`arm_id` 仅作诊断标注。**`C3_Status` 对称扩展**：加入 `arms[].eef_pose`、`arms[].health`。**`C3_EStop` 扩展**：加入 `arm_id` 诊断字段（标注触发来源臂；停止范围保持全局）。**安全规则补充**：PlanGate 安全、规划预览有效期、向后兼容性声明（§9） |