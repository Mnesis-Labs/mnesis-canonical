# xr_bridge WebSocket 消息 SPEC 摘要

> **所属契约**: C3 — xr_bridge WS（详情见 `XR_ROBOT_CONTRACT.md`）
> **版本**: v1.4
> **本文件**: xr_bridge WebSocket 消息格式的简洁摘要，供快速参考。完整协议细节和语义见 `XR_ROBOT_CONTRACT.md`。

---

## 传输层

```
WebSocket (WSS)  |  JSON 文本帧  |  UTF-8
```

## 公共消息头

```json
{
  "type": "<message_type>",
  "seq":  <uint32>,
  "ts":   <int64>,
  "body": { ... }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | string | 消息类型标识 |
| `seq` | uint32 | 发送方单调递增序列号 |
| `ts` | int64 | 发送方 Unix 纳秒时间戳 |

## 消息类型一览

| 方向 | 类型 | 方向 | 触发时机 |
|---|---|---|---|
| `C3_Info` | 机器 → VR | 连接建立后立即发送 | 机器人规格和能力 |
| `C3_Bind` | VR → 机器 | 连接/重连后 | 选择被控臂 |
| `C3_Bound` | 机器 → VR | 绑定确认 | 确认 + 初始位姿 |
| `C3_Frame` | VR → 机器 | 循环发送（60–90 Hz） | 遥操作控制帧 |
| `C3_Status` | 机器 → VR | 循环发送（30–60 Hz） | 状态回传 |
| `C3_EStop` | 双向 | 任一方向触发 | 急停闩锁 |
| `C3_Heartbeat` | 双向 | 周期性（100 ms） | 看门狗 |
| `C3_Reset` | VR → 机器 | 急停后恢复 | 清除闩锁 + 重锚定 |

## 消息 body 结构

### C3_Info (机器 → VR)

```json
{
  "robot_name": "string",
  "arms": [{"name": "string", "dof": int, "joint_names": ["string"]}],
  "protocol_version": "string",
  "can_estop": bool,
  "watchdog_timeout_ms": int
}
```

### C3_Bind (VR → 机器)

```json
{"arm": "string"}
```

### C3_Bound (机器 → VR)

```json
{
  "arm": "string",
  "initial_joint_positions": [float],
  "initial_pose_SE3": [float × 7]
}
```

### C3_Frame (VR → 机器)

```json
{
  "target_pose_SE3": [float × 7],
  "gripper": float,
  "mode": "position" | "joint"
}
```

### C3_Status (机器 → VR)

```json
{
  "joint_positions": [float],
  "joint_velocities": [float],
  "pose_SE3": [float × 7],
  "gripper": float,
  "executing": bool,
  "error": "string | null"
}
```

### C3_EStop (双向)

```json
{
  "reason": "operator_triggered" | "watchdog_timeout" | "joint_limit_exceeded" | "communication_loss" | "internal_error",
  "source": "vr" | "robot"
}
```

### C3_Heartbeat (双向)

```json
{"counter": uint32}
```

### C3_Reset (VR → 机器)

```json
{"ack": true}
```

## 关键参数

| 参数 | 默认值 |
|---|---|
| 看门狗超时 | 500 ms（由机器在 `C3_Info` 宣告） |
| 心跳间隔 | 100 ms |
| 控制帧速率 | 60–90 Hz |
| 状态回传速率 | 30–60 Hz |
| 末端速度软限 | ≤ 2 m/s |
| 重连退避 | 100ms → 500ms → 2s → 5s（cap） |

## 坐标约定

- 右手系, Y-up, 米, 四元数 {x, y, z, w}（标量最后）

## 相关

- 完整协议文档: [`XR_ROBOT_CONTRACT.md`](XR_ROBOT_CONTRACT.md)
- 跨仓契约登记簿: [`CONTRACTS.md`](../CONTRACTS.md)