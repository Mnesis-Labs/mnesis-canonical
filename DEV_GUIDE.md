# DEV_GUIDE — mnesis-canonical 开发指引

> **本仓唯一开发约定入口。** 合并自原 `CLAUDE.md` 与本仓 CI/测试/发布约定。
> 契约只读：`contracts/` 与 `*.lock` 不在此档直接修改，走 `type:contract-change` 流程。

---

## 1. Agent 纪律

| 项 | 规则 |
|---|---|
| 角色 | 本仓 worker，只处理指派的单个 issue |
| 边界锁 | 只改本仓文件；对兄弟仓的意见用 `gh issue create --repo Mnesis-Labs/Parthenon` 提案，禁止直接改其他仓 |
| 契约只读 | `contracts/` 与 `*.lock` 需改动则在 PR 说明并停下，等 PM 走 `type:contract-change` 流程 |
| 栈 | Python 纯标准库（开放标准：schema / validate / io / lerobot / isaac / manifest） |
| 测试纪律 | 合并前必须通过 `ruff check .` 与 `pytest -q` |
| 提交 | 分支 `agent/issue-<N>`；PR 含 `Closes #<N>` + 验收自查 |
| 可信状态 | merged / CI 等断言以 `gh api` 真实返回为准 |
| 完成 | 改代码 → 本地测试通过 → 开 PR → 停止（评审与合并不归你管） |

### 真机文档铁律（2026-07-27）

**真机操作步骤只写在 Parthenon 的 `HARDWARE-OPERATIONS.md`** —— 唯一入口，本仓不另起操作手册。

- 本仓可保留**深度技术细节**（排障原理、协议规格、硬件参数），但**上机操作步骤**必须写进 Parthenon 那一份，并在其 §7 来源台账登记本仓文档。
- 新增真机验证项 → 开 issue 打 `needs:hw-verify`，自动汇聚进 Parthenon `VERIFICATION.md`。
- 测试结果回填 → Parthenon `DEVICE_TESTING.md`。

理由：真机操作曾散落 5 个仓 12 份文档（含已过时路径如 `TeleOP-Alohamini`），上机时翻找成本高且容易照着过时步骤操作。

---

## 2. 安装与使用

```bash
pip install -e ".[dev]"
```

Python：
```python
from mnesis_canonical import read_jsonl, validate_frames
report = validate_frames(read_jsonl("episodes/ep_0/data.jsonl"))
print(report.ok, report.total, report.errors)
```

CLI（CI/ingest 门禁，exit 0/1/2）：
```bash
python -m mnesis_canonical validate episodes/ep_0/data.jsonl
# 或：mnesis-canonical validate ...
```

LeRobot 列式往返：
```python
from mnesis_canonical import to_lerobot, from_lerobot
columns = to_lerobot(read_jsonl("episodes/ep_0/data.jsonl"))
frames = from_lerobot(columns)
```

可选 JSON Schema 后端：`pip install "mnesis-canonical[jsonschema]"`，`validate_frame_jsonschema(frame)`。

---

## 3. Device Adapter SDK

`mnesis_canonical.sdk` 为所有采集面提供统一接口。每个 adapter 实现 `open()` / `close()` / `read_frame()` → `CanonicalFrame`，支持迭代与上下文管理器。

```python
from mnesis_canonical.sdk import QuestAdapter, RobotAdapter

with QuestAdapter() as quest:
    for frame in quest:
        print(frame.index, frame.source_device, frame.action)

with RobotAdapter() as robot:
    frame = robot.read_frame()
    print(frame.observation_state)
```

---

## 4. 测试与 lint（CI 跑什么）

```bash
ruff check . && pytest -q
```

| CI job | 内容 |
|---|---|
| `ci.yml` — 完整流水线 | 全量 `pytest` + `ruff` + release-check §2–§6 |
| `ci-fast.yml` | 快速路径（无状态检查） |
| `agent-review.yml` | agent 自检 |

`ruff` 配置（`pyproject.toml`）：line-length 100, target `py310`, select `E/F/I/UP/B`。
`pytest`：`testpaths = ["tests"]`, `pythonpath = ["."]`, marker `slow`。

---

## 5. 发布流程

> 机器可执行部分由 `scripts/release_check.py` 自动校验（`--only` 可局部跑）。

```bash
python scripts/release_check.py          # §1–§6 全部
python scripts/release_check.py --only version
python scripts/release_check.py --only contracts
python scripts/release_check.py --only embodiments
python scripts/release_check.py --only lint
python scripts/release_check.py --only tests
python scripts/release_check.py --only smoke
```

### §1 版本号（`scripts/version_check.py` 门禁 #76）

三个字符串必须一致：`mnesis_canonical/__init__.py` `__version__`、`pyproject.toml` `[project] version`、`CHANGELOG.md` preamble 的 `**Package x.y.z**`。

手动部分：`CHANGELOG.md` 把 `[Unreleased]` 移到新版本标题下，底部加 `[x.y.z]:` 对比链接。

### §2 契约完整性
```bash
python -m mnesis_canonical.contracts_check   # exit 0
```
契约变更需重新生成 `contracts/contracts.lock`，走 PM `type:contract-change` 流程。

### §3 Embodiment 登记表
```bash
python -m mnesis_canonical.embodiment_check   # exit 0
```
所有 `embodiments/*.json` 须通过 `embodiment.schema.json` 校验。

### §4 Lint & 类型检查
```bash
ruff check .      # 无错误
pyright .         # 零类型错误（dev deps 中安装时）
```

### §5 测试
```bash
pytest -q
pytest -q -m slow
```

### §6 冒烟测试
```bash
python -m mnesis_canonical --help
python -m mnesis_canonical validate examples/episode_0/data.jsonl
python -m mnesis_canonical.importers --help
python -m mnesis_canonical.importers list
```

### §7 Git & tag（人工）
- 所有变更提交到 `main`
- `git tag -a v<version> -m "v<version>"`
- `git push origin main --tags`

### §8 GitHub Release + PyPI（自动）

推 tag 即触发 `.github/workflows/release.yml`：版本守卫（tag vs 树里三个字符串）
→ release_check §2–§6 → build → `twine check --strict` → **干净 venv 里装 wheel 跑
CLI** → 建 GitHub Release → 发 PyPI。

tag 已经存在、需要补发时（比如 workflow 晚于 tag 落地）：

```bash
gh workflow run release.yml -f tag=v0.5.0 -f dry_run=true   # 空跑：只校验+构建
gh workflow run release.yml -f tag=v0.5.0                   # 确认后真发
```

`dry_run` 不是可选的礼貌：**PyPI 上传不可撤销**，同一版本号发错只能 yank，
不能覆盖重发。没跑过的发布路径先空跑一次。

### §9 PyPI Trusted Publishing（一次性人工前置）

发布不用 `PYPI_TOKEN` secret，用 OIDC —— 仓里零凭据，也就没有「secret 到底设没
设」这种从仓外看不见的机器状态（#109 卡了一轮就是卡在这上面）。

首次发布前，有 PyPI 账号的人到
<https://pypi.org/manage/account/publishing/> 建一个 **pending publisher**
（项目还不存在时走这个入口，首次上传自动建项目）：

| 字段 | 值 |
|---|---|
| PyPI Project Name | `mnesis-canonical` |
| Owner | `Mnesis-Labs` |
| Repository name | `mnesis-canonical` |
| Workflow name | `release.yml` |
| Environment name | **留空**（本 workflow 不用 environment，填了会对不上而拒签） |

配完跑一次 §8 的补发命令即可。验收判据只有一条 —— 不是流水线绿了，是：

```bash
pip install mnesis-canonical && python -c "import mnesis_canonical; print(mnesis_canonical.__version__)"
```

---

## 6. 文档大赦（文档收敛规则）

本仓收敛到**三份主干文档**：

| 文件 | 管什么 |
|---|---|
| `ROADMAP.md` | 做什么、什么顺序 |
| `PRD.md` | 做成什么样（验收判据） |
| `DEV_GUIDE.md` | 怎么做（CI/测试/发布/agent 约定）—— 本文件 |

其余归档进 `docs/_archive/<date>/`，加 front-matter `archived` + `superseded_by`。**不许直接删**。

### 安全前提（必读）

归档前**必须**：
1. `git grep -l "<文件名>"` 在本仓复核，任何代码文件命中 → `keep-as-is`，不许归档。
2. 确认未被服务/CI/脚本用路径直接读取。
3. 不确定就留着不动，宁可少归档，不可错删活文件。

---

## 7. 跨仓依赖

- **数据消费者**：Iris（手机采集）· Eidolon（Quest 前端）· Daedalus（机器人执行/训练）· Ambrosia（数据平台/控制台）
- **变更顺序**：本仓（SPEC + 参考实现）先改 → 消费方同步，永不 fork 字段
- **兼容性承诺**：additive = minor；breaking = major + 迁移说明（见 `PRD.md` §Versioning）