# canonical v1.0 发布 checklist（三件套）

> 状态：草案（D-19a 随件产出）。**发布时点由 Muso 最终确认**；本文档只固化“发什么 / 怎么发”，不代表已发布。
> 关联：D-18 之后排期；benchmark 博客与视频线**解耦、后补**，不阻塞 v1.0。

## 1. 发布内容清单（v1.0 三件套）

v1.0 发布包 = 一次打出的三件套：

### ① Spec 定稿
- [ ] `SPEC.md` — canonical frame 定稿（profiles：`ego_v1` / `robot_v2`）。
- [ ] `mnesis_canonical/canonical_frame.schema.json` — JSON Schema，`$id` 版本号与 `SPEC.md`、`schema.py` 三方对齐。
- [ ] `contracts/` 与 `*.lock` — 契约冻结；任何改动走 PM `type:contract-change`，不在本件内。
- [ ] `taxonomies/manipulation_v1.json` — 操作动作分类（spans 契约）。
- [ ] `embodiments/*.json` + `embodiment.schema.json` — embodiment registry 打包进 wheel（consumer `load_embodiment` 可读）。
- [ ] `CHANGELOG.md` — 标注 v1.0 条目。

### ② LeRobot / RLDS 双导出
- [ ] `mnesis-canonical convert --to lerobot` — 列式 JSON 导出冒烟通过。
- [ ] RLDS/Isaac 导出（`mnesis-canonical convert --to isaac`）冒烟通过。
- [ ] 双导出在示例 episode 上端到端跑通（见 `examples/`）。

### ③ HF 示例集
- [ ] `examples/` 下 episode 全部过 conformance（`mnesis-canonical validate`）。
- [ ] 生态导入器示例：XRoboToolkit pickle → canonical，含 `import_meta.json` 质量分卡片输入（D-19a，本件）。
- [ ] HF 数据集卡片（README + LICENSE Apache-2.0）就绪。
- [ ] 示例集**只含合成/自造数据**，不含任何第三方真实数据。

### 生态导入器（D-19a，随三件套）
- [x] `mnesis-import xrobotoolkit <teleop_log_*.pkl>` — pickle 核心导入器 + 字段映射表 + 缺失字段填充策略（`import_meta.json` 显式声明 `source=imported_xrobotoolkit` + quality 降档）。
- [x] `--format airbot-mcap` 第二输入（airbot_ie/AIRDC `.mcap`）冒烟通过（合成 fixture）。
- [ ] **后补（不阻塞 v1.0）**：真实 airbot `.mcap` 的 FlatBuffers 消息解码（当前 smoke 路径读 json-encoded MCAP 消息，见 `mnesis_canonical/importers/_mcap.py`）。

## 2. 发布步骤（发布时点待 Muso 确认）

1. [ ] 冻结版本号：`pyproject.toml` `version` → `1.0.0`；`mnesis_canonical/__init__.py` `__version__` 同步。
2. [ ] 绿灯门禁：`ruff check .` 与 `pytest -q` 全绿（合并前必过）。
3. [ ] 契约核对：`mnesis-canonical-contracts-check` 通过；`contracts/*.lock` 无未走流程的漂移。
4. [ ] 更新 `CHANGELOG.md`：v1.0 条目 + 日期。
5. [ ] 构建 wheel/sdist：`python -m build`；确认 `embodiments/*.json` 与 schema 已随 wheel 打包（`test_wheel_install.py` 覆盖）。
6. [ ] 转 public / 发 PyPI：按 Muso 拍板（当前仓库状态见 memory `project-state-2026-07`）。
7. [ ] 推 HF 示例集数据卡片。
8. [ ] 打 tag `v1.0.0` + GitHub Release，正文引用本 checklist。
9. [ ] **后补线（解耦）**：benchmark 博客、视频。

## 3. 验收对照（D-19a 本件）

- [x] 合成 fixture pickle 端到端转出合法 canonical episode（过 conformance）。
- [x] mcap 路径冒烟（合成 fixture）。
- [x] 发布 checklist 入 `docs/`。
