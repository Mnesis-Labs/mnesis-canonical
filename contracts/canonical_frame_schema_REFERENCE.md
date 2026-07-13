# Canonical Frame Schema — 引用说明

> **所属契约**: C1 — Canonical Frame Schema
> **版本**: v0.1
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

| 字段 | 类型 | 长度 | 说明 |
|---|---|---|---|
| `index` | int | — | 全局单调帧序号 |
| `episode_index` | int | — | Episode ID |
| `task_index` | int | — | 任务序号（单任务 = 0） |
| `frame_index` | int | — | 帧内序号（0-based，严格递增） |
| `t_ns` | int | — | 墙钟纳秒 |
| `t_hw_ns` | int | — | 硬件纳秒（pose↔video join key） |
| `timestamp` | str | — | ISO-8601 墙钟时间 |
| `head_pose_SE3` | float[7] | 7 | 头部位姿 [tx,ty,tz, qx,qy,qz,qw] |
| `observation.state` | float[7] | 7 | 7-DoF 状态 |
| `observation.images.ego` | str | — | ego 视频帧引用 |
| `action` | float[6] | 6 | 相对增量 [tx,ty,tz, rx,ry,rz] |
| `spatial_anchor_id` | str\|null | — | 空间锚点 ID |
| `source.device` | str | — | 采集设备（phone/glasses/quest/pico/robot/sim） |
| `source.modality` | str | — | 采集模态（ego_human/teleop/robot_replay/sim） |
| `tracking_state` | str | — | 跟踪状态 |

## 相关

- 完整规范: [`SPEC.md`](../SPEC.md)
- 参考实现: `mnesis_canonical/`
- 跨仓契约登记簿: [`CONTRACTS.md`](../CONTRACTS.md)