# Canonical Frame Schema — 引用说明

> **所属契约**: C1 — Canonical Frame Schema
> **版本**: v0.2（additive-only; v0.1 帧仍通过校验）
> **additive 增补**: 夹爪观测通道 `observation.gripper[.left|.right]`（闭合程度 [0.0,1.0]，`0.0`=完全张开 / `1.0`=完全闭合，可选；方向与 `action.gripper`、C3 `arms[].gripper` 一致）；新 profile `ego_multicam_v1`（多相机 ego 图像键集，相机名取自 embodiment registry `capture.cameras[].name`）
> **定义方**: canonical（本仓）
> **消费方**: Iris · Eidolon · Daedalus · Ambrosia

---

## 权威文件位置

Canonical Frame Schema 的 JSON Schema 定义位于本仓以下路径：

```
mnesis_canonical/canonical_frame.schema.json
```

该文件是 Canonical Frame 数据格式的**权威 JSON Schema**（JSON Schema 2020-12），定义了每一帧的字段名、类型、取值范围和必填约束。

## 配套规范

| 文件 | 说明 |
|---|---|
| `mnesis_canonical/canonical_frame.schema.json` | JSON Schema 定义（机器可读） |
| `SPEC.md`（本仓根目录） | 人类可读的字段规范（字段含义、约定、兼容性） |
| `mnesis_canonical/schema.py` | Python 参考实现（`CanonicalFrame` 类型、向量长度、设备词表） |
| `mnesis_canonical/validate.py` | Python 校验器（`validate_frame` / `validate_frames`） |

## 校验方法

### Python

```python
from mnesis_canonical import validate_frame, validate_frames, read_jsonl

# 单帧校验
frame = {"index": 0, "episode_index": 0, ...}
report = validate_frame(frame)
print(report.ok)  # True / False

# 完整文件校验
frames = read_jsonl("episodes/ep_0/data.jsonl")
report = validate_frames(frames)
print(f"total={report.total} valid={report.valid} errors={len(report.errors)}")
```

### 命令行

```bash
python -m mnesis_canonical validate episodes/ep_0/data.jsonl
```

### 通用（任意语言，使用 JSON Schema 文件）

```bash
# 使用 jsonschema CLI（需安装）
pip install "mnesis-canonical[jsonschema]"
check-jsonschema --schemafile mnesis_canonical/canonical_frame.schema.json episodes/ep_0/data.jsonl
```

## 字段一览

| 字段 | 类型 | 长度 | profile | 说明 |
|---|---|---|---|---|
| `index` | int | — | *all* | 全局单调帧序号 |
| `episode_index` | int | — | *all* | Episode ID |
| `task_index` | int | — | *all* | 任务序号（单任务 = 0） |
| `frame_index` | int | — | *all* | 帧内序号（0-based，严格递增） |
| `t_ns` | int | — | *all* | 墙钟纳秒 |
| `t_hw_ns` | int | — | *all* | 硬件纳秒（pose↔video join key） |
| `timestamp` | str | — | *all* | ISO-8601 墙钟时间 |
| `head_pose_SE3` | float[7] | 7 | *all* | 头部位姿 [tx,ty,tz, qx,qy,qz,qw] |
| `observation.state` | float[N] | 7 or N | *all* | 7-DoF (ego_v1 / ego_multicam_v1) 或 N-DoF (robot_v2) |
| `observation.images.ego` | str | — | ego_v1 | ego 视频帧引用（`ego_multicam_v1` 中 = 名为 `ego` 的那一路，需 embodiment 声明） |
| `observation.images.<cam>` | str | — | robot_v2 / ego_multicam_v1 | 开放相机键集；`robot_v2` 自由键，`ego_multicam_v1` 相机名须在 embodiment `capture.cameras[].name` 内 |
| `action` | float[N] | 6 or N | *all* | 相对增量 (ego_v1 / ego_multicam_v1 为 6) 或变长 (robot_v2) |
| `observation.eef_pose.left` | float[7] | 7 | robot_v2 opt | 左末端执行器位姿 |
| `observation.eef_pose.right` | float[7] | 7 | robot_v2 opt | 右末端执行器位姿 |
| `action.gripper` | float | — | *all* opt | 夹爪闭合程度 [0.0,1.0]（`0.0`=完全张开，`1.0`=完全闭合）；指令侧 |
| `observation.gripper` | float | — | *all* opt | 夹爪闭合程度 [0.0,1.0]（`0.0`=完全张开，`1.0`=完全闭合）；单/主夹爪，方向与 `action.gripper` 一致 |
| `observation.gripper.left` | float | — | robot_v2 opt | 左夹爪闭合程度 [0.0,1.0]（`0.0`=完全张开，`1.0`=完全闭合）；双臂 |
| `observation.gripper.right` | float | — | robot_v2 opt | 右夹爪闭合程度 [0.0,1.0]（`0.0`=完全张开，`1.0`=完全闭合）；双臂 |
| `observation.hand.left` | float[3K] | 3×K | *all* opt | **[experimental]** 左手关节**位置**，展平 `[x0,y0,z0,…]`，米；`K` = `observation.hand.layout` 的 `joint_count`。**手不在场时整键省略**（不发零向量、不发 null） |
| `observation.hand.right` | float[3K] | 3×K | *all* opt | **[experimental]** 右手关节位置，同上 |
| `observation.hand.left.rot` | float[4K] | 4×K | *all* opt | **[experimental]** 左手关节**朝向**，展平四元数 **{x,y,z,w}**；仅原生提供朝向的来源填（MediaPipe 类不填） |
| `observation.hand.right.rot` | float[4K] | 4×K | *all* opt | **[experimental]** 右手关节朝向，同上 |
| `observation.hand.layout` | str | — | *all* opt | **[experimental]** 骨架布局 id（`skeletons/<id>.json`），如 `mediapipe_hand_21` / `webxr_hand_25` / `openxr_hand_26`。**有关键点时必填** |
| `observation.hand.frame` | str | — | *all* opt | **[experimental]** `world` / `head_anchored` / `hand_local` —— 关键点所在参考系，**有关键点时必填**。`head_anchored` = 手内自洽、手相对世界的绝对位置**不可信** |
| `observation.hand.source` | str | — | *all* opt | **[experimental]** 溯源标签（开放集），如 `mediapipe_world+arcore_pose`。**只管溯源**，几何语义在 `observation.hand.frame` |
| `spatial_anchor_id` | str\|null | — | *all* | 空间锚点 ID |
| `profile` | str | — | *all* opt | 可选; `ego_v1` (默认) / `robot_v2` / `ego_multicam_v1` |
| `embodiment_id` | str\|null | — | *all* opt | 引用 embodiment registry |
| `source.device` | str | — | *all* | 采集设备（phone/glasses/quest/pico/robot/sim） |
| `source.modality` | str | — | *all* | 采集模态（ego_human/teleop/robot_replay/sim） |
| `tracking_state` | str | — | *all* | 跟踪状态 |

## 相关

- 完整规范: [`SPEC.md`](../SPEC.md)
- 参考实现: `mnesis_canonical/`
- 跨仓契约登记簿: [`CONTRACTS.md`](../CONTRACTS.md)