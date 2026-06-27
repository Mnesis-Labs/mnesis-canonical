# Sprint S1 · mnesis-canonical（Cline 连续冲刺 → 下周 demo）

> Tech Lead 授权 Cline **连续执行**：每个 Task `ruff check . && pytest -q` 真绿就 commit，接着下一个；只有①自测红修不动 ②需改标准/字段决策 ③Sprint 完成 时停下写 HANDOFF。
> 背景已就绪（schema/validate/io/tests/SPEC/README 已由 Tech Lead 搭好，8 tests 绿）。本冲刺把它打磨到"可作标准对外 + 喂 Ambrosia ingest + 跨采集面"。

## 0. 铁律
1. 完成 = `ruff check . && pytest -q` 真绿 + 贴测试数。**不许空壳/未测冒充完成。**
2. **契约先于代码**：改字段先改 `SPEC.md` + JSON Schema，再改 Python + 测试，HANDOFF 标注下游同步。
3. 一任务一 commit；不合并 main；绝不提交密钥/数据。

## 1. 任务（按序）
- **C1 · JSON Schema 文件**：新建 `mnesis_canonical/canonical_frame.schema.json`（与 `schema.py`/`SPEC.md` 完全一致的 JSON Schema Draft 2020-12）；`validate.py` 增加可选 `jsonschema` 后端（放 `extras`，缺省仍用纯逻辑）。测试：example 同时过两套校验。
- **C2 · CLI**：`python -m mnesis_canonical validate <path.jsonl>` 输出 total/valid/errors，非零退出码用于 CI。测试：对 example 通过、对坏样例非零。
- **C3 · LeRobot 适配器**：`to_lerobot(frames) -> dict/列式` + `from_lerobot(...)`，把扁平列映射到 LeRobot dataset features（observation.state/action/timestamp/episode_index/frame_index/index/task_index）。测试：round-trip。
- **C4 · 多采集面示例 + 词表**：新增 `examples/episode_quest/`（source.device=quest, modality=teleop）、`examples/episode_robot/`（device=robot, modality=robot_replay）各一条；确认 `validate_frames` 通过。固化 DEVICES/MODALITIES 词表 + SPEC 同步。
- **C5 · Isaac/GR00T 兼容说明**：在 `SPEC.md §Compatibility` 补与 Isaac Lab / GR00T 数据字段的逐项对照表（**不确定项标"待对齐 Parthenon 03 §3.2"，别擅自冻结**）。
- **C6 · 打包**：确保 `pip install mnesis-canonical` 可用（packages.find 正确）；README 加"作为标准引用"的版本/兼容承诺。

## 2. 完成标准（demo 级）
- `ruff check . && pytest -q` 全绿；example（phone/quest/robot 三采集面）均校验通过。
- CLI 可被 Ambrosia ingest 复用；LeRobot 适配器可 round-trip。
- 下游同步需求（EgoWear/Ambrosia 字段对齐）写入 HANDOFF 交 Tech Lead。
