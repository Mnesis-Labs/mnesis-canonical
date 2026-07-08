# Mnesis 跨仓契约登记簿（CONTRACTS.md）

> **规则**：任何跨仓接口，先在这里登记/改版本，再改代码；两侧仓库各自持有钉死该契约的测试。改契约的 PR 必须在描述里链接两侧测试。本文件由 Tech Lead（Claude Code）守门。
> 仓库：**Iris**=手机采集 · **Eidolon**=Quest VR 前端 · **Daedalus**=机器人执行/训练 · **Ambrosia**=数据平台/控制台 · **canonical**=本仓（数据标准）。

| # | 契约 | 版本 | Owner（定义方） | 消费方 | 两侧测试 |
|---|---|---|---|---|---|
| C1 | **Canonical Frame Schema**（JSONL 帧格式：字段/向量长/双时间戳/词表） | v0.1 | canonical（`SPEC.md` + `canonical_frame.schema.json`） | Iris·Eidolon·Daedalus·Ambrosia | canonical `tests/` · Iris `CanonicalSchemaContractTest` · Ambrosia ingest 校验 |
| C2 | **Episodes Ingest HTTP**（`POST /api/episodes` multipart：`manifest`+`jsonl`+`video?`+`frames?`；`X-App-Token?`） | v1.1 | Ambrosia（`docs/SPRINT_S4_CLINE.md` 契约节 + `docs/HANDOFF_S4.md`） | Iris·Eidolon·Daedalus | Ambrosia `tests/test_iris_contract.py`（Ct-1..11） · Iris `EpisodeUploaderHeaderTest`+S4 D2 |
| C2a | frames.zip 规范：根目录 `%06d.jpg`（与 `frame_index` 对齐，1fps）；包≤200MB/帧≤5MB/≤3600 帧。服务端宽容收 png/jpg/jpeg/webp/bmp，规范名以 jpg 为准 | v1.1 | Ambrosia | Iris（Eidolon/Daedalus 后续） | 同上 |
| C3 | **xr_bridge WS**（VR↔机器人实时遥操作：帧协议/急停闩锁/重连再锚定/看门狗） | v1.4 | Daedalus（`docs/integration/XR_ROBOT_CONTRACT.md`） | Eidolon | Daedalus harness + 坐标真值 fixture · Eidolon PH-2/PH-3 测试 |
| C4 | **Robot-Bridge API**（平台↔真机：关节读写/示教/安全），目的=把硬件控制留在 Daedalus、Ambrosia 只经 API 消费 | **草案 TBD** | Daedalus（待定义） | Ambrosia（`bridge/hw_bridge.py` 现状=临时直连，待迁移到本契约） | 待建 |
| C5 | **MJCF 仿真资产**（机器人/场景模型单一事实源） | **草案 TBD** | Daedalus（`simulation/mujoco/` = 物理事实源） | Ambrosia（网页 MuJoCo-WASM 查看器只做展示/回放） | 待建（资产版本号 + 校验和） |

## 职责分界（防重复建设）
- **物理/控制/训练归 Daedalus**：真机驱动、LeRobot 数据/训练、物理精确 MuJoCo、xr_bridge。
- **数据/展示/评测归 Ambrosia**：ingest→校验→质量门→标注→数据集/评测、控制台（含浏览器内 MuJoCo-WASM **回放与演示**）。
- Ambrosia 不长硬件驱动（现有 `bridge/hw_bridge.py` 为过渡，迁 C4）；Daedalus 不长数据平台 UI。
- 采集面（Iris/Eidolon）只产 Canonical 数据 + 消费 C2 上传，不 fork schema。

## 变更流程
1. 提案：在本文件对应行加「vNext 草案」+ 说明 → PR 到本仓。
2. 实现：Owner 仓先落 + 测试绿 → 消费方仓对齐 + 测试绿。
3. 收尾：本文件版本号定稿，两侧 PR 互链。
