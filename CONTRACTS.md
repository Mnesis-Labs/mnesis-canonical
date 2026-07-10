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

---

# Tech Lead 战略提案（2026-07-10）— 各仓自行决策,勿越权代改

> 以下是 Claude Code(Tech Lead·跨仓 CI)从数据飞轮全局给出的**建议**,写在这里供各仓 Cline/负责人阅读并**自行决定是否采纳**。契约类提案走上面「变更流程」;产品类由对应仓自行排期。

## A. 契约 vNext 提案(canonical 定义,各消费方对齐)

### C1-vNext · 帧加 `schema_version` + 溯源字段(强烈建议,外部采用/复现前必须)
现状 C1 帧无版本号、无溯源。建议每帧(或每 episode manifest)加:`schema_version`(如 `"1.0"`)、`capture_app`(iris/eidolon/daedalus)+ `app_version` + `git_sha`、`device_id`(匿名化)、`session_id`、`calibration_ref`(内参/外参版本)。
**价值**:① 数据格式演进可迁移(没版本号将来改字段=灾难);② 复现性/可追溯(数据公司的命脉——买家要知道每条数据"哪台设备、哪版 App、什么标定"出的);③ 调试跨设备问题的唯一抓手。**建议放 manifest 层(不涨每帧体积)+ 帧层只加 `schema_version`。**

### C6(新草案)· 跨设备时间同步(数据质量隐患,现在没人管)
`t_hw_ns` 是 pose↔video↔多设备的 join key,但**手机/机器人/Quest 三个时钟互相不对齐**——遥操作里"人手→机器人"的因果延迟、多视角融合全靠它。建议:每 session 记录一次**时钟偏移**(设备 vs 一个参考钟,NTP 或采集开始的握手)写进 manifest(`clock_offset_ns`),下游对齐时可校正。**Owner 待定(canonical 定义字段,各设备端各自测量);优先级:做多设备融合/遥操作因果分析前必须。**

### C7(新草案)· 数据集导出格式(Ambrosia S6-3 落地时定契约)
Ambrosia 的 LeRobot/Isaac 导出应成为**稳定契约**,让 Daedalus/外部训练直接消费,不各写各的。Owner=Ambrosia(复用 canonical `to_lerobot`),消费方=Daedalus 训练 + 外部。

## B. 各仓产品建议(对应仓自行排期,非契约)

| 仓 | 建议 | 为什么(飞轮/商业价值) |
|---|---|---|
| **Ambrosia** | **① 数据集"价值分"**:Themis 质量 → 每数据集一个可解释评分,直接当**对外定价信号**。② **覆盖缺口分析**:控制台告诉你"缺什么数据"(按任务/物体/光照/设备分布)→ 指挥下一步采集,这是飞轮的大脑。③ **回放即评测**:用 MuJoCo 回放算"录制动作是否物理可行/自洽"→ 自动质量门(物理对齐=护城河)。④ **PII 脱敏层**:ego 相机拍到人脸/屏幕/证件,卖数据前的脱敏+同意 = 法律必需 + 差异化。 | 把"质量"接到"商业化"与"采集指挥",而不止是存储看板 |
| **Daedalus** | **① 时间同步(见 C6)** 机器人端记录 `clock_offset_ns`。② **T3 上传带 `frames.zip`**(现在只 manifest+jsonl):机器人前视/腕视图打包,平台回放才有画面。③ **C5 MJCF 发版**:给模型加 `version+sha256` 发布,让 Ambrosia 忠实回放(S6-2 依赖)。 | 让机器人 episode 在平台"可回放、可对齐、有画面" |
| **Eidolon** | **① MI-1 Quest→Canonical 导出器 = 三采集面里唯一还缺的一面**,优先级应最高(手机✅/机器人✅ 都通了)。② 遥操作 episode 带手部/头显位姿 → `source.device=quest`,直接喂飞轮。 | 补齐第三条数据流,飞轮才"三面齐" |
| **Iris** | 见本仓 `docs/ROADMAP_IRIS.md`(GL 流畅度→溯源字段→离线可靠投递→端上回看→AR 眼镜形态)。 | — |

## C. 关键洞察:飞轮的"三面齐"已在临界点
手机(Iris)✅ 真机验过 · 机器人(Daedalus T3)✅ 上传器已做 · Quest(Eidolon MI-1)⛔ 唯一缺口。**建议把 Eidolon MI-1 + Ambrosia S6(收 3 面 + 忠实回放)+ Daedalus C5 发版 作为下一个跨仓"会师点"**,一次联测三面同屏 = 可对投资人演示的"真实数据飞轮"。
