# xr_bridge WebSocket 消息 SPEC 摘要

> **所属契约**: C3 — xr_bridge WS（详情见 `XR_ROBOT_CONTRACT.md`）
> **版本**: v1.6
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

| 类型 | 方向 | 触发时机 |
|---|---|---|
| `C3_Info` | 机器 → VR | 连接建立后立即发送，机器人规格和能力 |
| `C3_Bind` | VR → 机器 | 连接/重连后，选择被控臂 |
| `C3_Bound` | 机器 → VR | 绑定确认，确认 + 初始位姿 |
| `C3_Frame` | VR → 机器 | 循环发送（60–90 Hz），遥操作控制帧 |
| `C3_Status` | 机器 → VR | 循环发送（30–60 Hz），状态回传 |
| `C3_EStop` | 双向 | 任一方向触发，急停闩锁 |
| `C3_Heartbeat` | 双向 | 周期性（100 ms），看门狗 |
| `C3_Reset` | VR → 机器 | 急停后恢复，清除闩锁 + 重锚定 |
| `C3_GhostTrajectory` | 机器 → VR | 规划预览，降采样关节轨迹 + 末端轨迹点 |
| `C3_PlanStatus` | 机器 → VR | 规划状态变更，planning/ok/unreachable/collision/expired |
| `C3_ExecuteConfirm` | VR → 机器 | 确认执行，携带 goal_seq |
| `C3_CameraControl` | VR → 机器 | **v1.6** 相机控制协商，下发 `{camera_id,width,height,fps,bitrate,codec}` |
| `C3_CameraStatus` | 机器 → VR | **v1.6** 相机协商结果回报，实际生效参数 + 传输线 |

## 消息 body 结构

### C3_Info (机器 → VR)

```json
{
  "robot_name": "string",
  "arms": [{"name": "string", "dof": int, "joint_names": ["string"]}],
  "protocol_version": "string",
  "can_estop": bool,
  "watchdog_timeout_ms": int,
  "video_capabilities": {
    "transports": ["mjpeg", "webrtc"],
    "codecs": ["mjpeg", "h264"],
    "cameras": ["head", "wrist_left", "wrist_right"]
  }
}
```

> `video_capabilities`（**v1.6 可选**）：视频传输能力声明。`transports` 顺序 = 偏好优先级（`mjpeg` 已落地 / `webrtc` 为 [DQ-1] 预留）。缺省等价 `{"transports":["mjpeg"]}`，向后兼容 ≤v1.5。

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
  "arms": [
    {
      "arm_id": "string",
      "target_pose_SE3": [float × 7],
      "gripper": float,
      "clutch": bool
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `arms` | array | **双臂数组信封**。单臂端发送 1 元素数组，向后兼容 v1.2 |
| `arms[].arm_id` | string | 臂标识（如 `"left"` / `"right"` / `"main"`） |
| `arms[].target_pose_SE3` | float[7] | 末端目标位姿（米 + 四元数 {x,y,z,w}） |
| `arms[].gripper` | float | 夹爪开度 [0.0, 1.0] |
| `arms[].clutch` | bool | clutch 脱开状态：true = 脱开（不跟随指令） |

### C3_Status (机器 → VR)

```json
{
  "arms": [
    {
      "arm_id": "string",
      "joint_positions": [float],
      "joint_velocities": [float],
      "eef_pose": [float × 7],
      "gripper": float,
      "health": "ok" | "warning" | "error"
    }
  ],
  "executing": bool,
  "error": "string | null"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `arms` | array | **双臂数组信封**。单臂端发送 1 元素数组，向后兼容 v1.2 |
| `arms[].arm_id` | string | 臂标识 |
| `arms[].joint_positions` | float[N] | 各关节当前角度（rad） |
| `arms[].joint_velocities` | float[N] | 各关节当前速度（rad/s） |
| `arms[].eef_pose` | float[7] | 末端当前位姿（米 + 四元数） |
| `arms[].gripper` | float | 夹爪当前开度 |
| `arms[].health` | string | 臂级健康状态：`ok` / `warning` / `error` |
| `executing` | bool | 全局执行状态 |
| `error` | string\|null | 全局错误信息 |

### C3_EStop (双向)

```json
{
  "reason": "operator_triggered" | "watchdog_timeout" | "joint_limit_exceeded" | "communication_loss" | "internal_error",
  "source": "vr" | "robot",
  "arm_id": "string | null"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `arm_id` | string\|null | 若为逐臂触发，指明具体臂；`null` 表示全局急停 |

### C3_Heartbeat (双向)

```json
{"counter": uint32}
```

### C3_Reset (VR → 机器)

```json
{"ack": true}
```

### C3_GhostTrajectory (机器 → VR)

```json
{
  "arm_id": "string",
  "goal_seq": uint32,
  "joint_waypoints": [[float], ...],
  "eef_waypoints": [[float × 7], ...],
  "duration_ms": uint32
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `arm_id` | string | 目标臂标识 |
| `goal_seq` | uint32 | 规划目标序列号（与 `C3_PlanStatus` / `C3_ExecuteConfirm` 联动） |
| `joint_waypoints` | float[N][] | 降采样关节轨迹点序列（每点 = float[N] 关节角度） |
| `eef_waypoints` | float[7][] | 末端轨迹点序列（每点 = 位姿） |
| `duration_ms` | uint32 | 轨迹预计执行时长（毫秒） |

### C3_PlanStatus (机器 → VR)

```json
{
  "arm_id": "string",
  "goal_seq": uint32,
  "status": "planning" | "ok" | "unreachable" | "collision" | "expired",
  "message": "string | null"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `arm_id` | string | 目标臂标识 |
| `goal_seq` | uint32 | 规划目标序列号 |
| `status` | string | 规划状态：`planning`（规划中）、`ok`（可达）、`unreachable`（不可达）、`collision`（碰撞）、`expired`（预览过期） |
| `message` | string\|null | 可读说明 |

### C3_ExecuteConfirm (VR → 机器)

```json
{
  "arm_id": "string",
  "goal_seq": uint32
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `arm_id` | string | 目标臂标识 |
| `goal_seq` | uint32 | 确认执行的规划目标序列号 |

### C3_CameraControl (VR/头显 → 机器, v1.6)

相机控制协商请求。语义对齐业界 `OPEN_CAMERA` 式协议，走本契约 WS 信封。

```json
{
  "camera_id": "string",
  "width": int,
  "height": int,
  "fps": int,
  "bitrate": int,
  "codec": "mjpeg | h264"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `camera_id` | string | 目标相机（对应 `C3_Info.video_capabilities.cameras`） |
| `width` / `height` | int | 请求分辨率（像素） |
| `fps` | int | 请求帧率 |
| `bitrate` | int | 请求目标码率（bps）；`mjpeg` 可忽略 |
| `codec` | string | 请求编码（属于 `video_capabilities.codecs`） |

### C3_CameraStatus (机器 → VR, v1.6)

对 `C3_CameraControl` 的应答，回报实际生效参数与传输线。

```json
{
  "camera_id": "string",
  "accepted": bool,
  "width": int,
  "height": int,
  "fps": int,
  "bitrate": int,
  "codec": "mjpeg | h264",
  "transport": "mjpeg | webrtc",
  "message": "string | null"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `camera_id` | string | 相机标识 |
| `accepted` | bool | 是否接受请求（`false` = 就近回退/拒绝） |
| `width`/`height`/`fps`/`bitrate`/`codec` | 见上 | **实际生效**参数（可能被 clamp） |
| `transport` | string | 实际视频线：`mjpeg` / `webrtc` |
| `message` | string\|null | 可读说明（可选） |

## 关键参数

| 参数 | 默认值 |
|---|---|
| 看门狗超时 | 500 ms（由机器在 `C3_Info` 宣告） |
| 心跳间隔 | 100 ms |
| 控制帧速率 | 60–90 Hz |
| 状态回传速率 | 30–60 Hz |
| 末端速度软限 | ≤ 2 m/s |
| 重连退避 | 100ms → 500ms → 2s → 5s（cap） |
| 规划预览有效期 | 30 s（过期后 `C3_PlanStatus` 状态变为 `expired`） |

## 安全规则

- **逐臂看门狗**：每臂独立维护看门狗计时器。某臂超时触发该臂 `C3_EStop`（带 `arm_id`），不影响其他臂。
- **全局急停**：`C3_EStop` 不带 `arm_id` 或 `reason` 为 `"operator_triggered"` 时，所有臂立即停止。
- **速度限制**：机器人端应实现末端速度软限（默认 ≤ 2 m/s）。
- **关节限位**：机器人端应拒绝超出物理关节限位的指令。
- **断线保护**：WebSocket 断开后所有臂自动停止运动。

## 向后兼容性

- v1.2/v1.3/v1.4 客户端忽略 `C3_GhostTrajectory`、`C3_PlanStatus`、`C3_ExecuteConfirm` 消息即可正常工作。
- 单臂端发送 `C3_Frame` 时使用 `arms: [{arm_id: "main", ...}]` 1 元素数组，与 v1.5 服务端完全兼容。
- ≤v1.5 客户端忽略 `C3_CameraControl` / `C3_CameraStatus` 消息与 `C3_Info.video_capabilities` 字段即可正常工作（v1.6 additive）。
- 新增字段均为可选/扩展，不破坏现有消息结构。

## 坐标约定

- 右手系, Y-up, 米, 四元数 {x, y, z, w}（标量最后）

## 相关

- 完整协议文档: [`XR_ROBOT_CONTRACT.md`](XR_ROBOT_CONTRACT.md)
- 跨仓契约登记簿: [`CONTRACTS.md`](../CONTRACTS.md)