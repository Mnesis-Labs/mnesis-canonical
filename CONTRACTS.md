# Mnesis 跨仓契约登记簿（CONTRACTS.md）

> **规则**：任何跨仓接口，先在这里登记/改版本，再改代码；两侧仓库各自持有钉死该契约的测试。改契约的 PR 必须在描述里链接两侧测试。本文件由 Tech Lead（Claude Code）守门。
> 仓库：**Iris**=手机采集 · **Eidolon**=Quest VR 前端 · **Daedalus**=机器人执行/训练 · **Ambrosia**=数据平台/控制台 · **canonical**=本仓（数据标准）。

| # | 契约 | 版本 | Owner（定义方） | 消费方 | 两侧测试 |
|---|---|---|---|---|---|
| C1 | **Canonical Frame Schema**（JSONL 帧格式：字段/向量长/双时间戳/词表） | v0.1 | canonical（`SPEC.md` + `canonical_frame.schema.json`） | Iris·Eidolon·Daedalus·Ambrosia | canonical `tests/` · Iris `CanonicalSchemaContractTest` · Ambrosia ingest 校验 |
| C2 | **Episodes Ingest HTTP**（`POST /api/episodes` multipart：`manifest`+`jsonl`+`video?`+`frames?`；`X-App-Token?`） | v1.1 | Ambrosia（`docs/SPRINT_S4_CLINE.md` 契约节 + `docs/HANDOFF_S4.md`） | Iris·Eidolon·Daedalus | Ambrosia `tests/test_iris_contract.py`（Ct-1..11） · Iris `EpisodeUploaderHeaderTest`+S4 D2 |
| C2a | frames.zip 规范：根目录 `%06d.jpg`（与 `frame_index` 对齐，1fps）；包≤200MB/帧≤5MB/≤3600 帧。服务端宽容收 png/jpg/jpeg/webp/bmp，规范名以 jpg 为准 | v1.1 | Ambrosia | Iris（Eidolon/Daedalus 后续） | 同上 |
| C3 | **xr_bridge WS**（VR↔机器人实时遥操作：帧协议/急停闩锁/重连再锚定/看门狗/双臂数组信封/PlanGate/相机控制协商/视频能力声明） | v1.6 | Daedalus（`docs/integration/XR_ROBOT_CONTRACT.md`） | Eidolon | Daedalus harness + 坐标真值 fixture · Eidolon PH-2/PH-3 测试 |
| C4 | **Robot-Bridge API**（平台↔真机：关节读写/示教/安全），目的=把硬件控制留在 Daedalus、Ambrosia 只经 API 消费 | **草案 TBD** | Daedalus（待定义） | Ambrosia（`bridge/hw_bridge.py` 现状=临时直连，待迁移到本契约） | 待建 |
| C5 | **MJCF 仿真资产**（机器人/场景模型单一事实源） | **草案 TBD** | Daedalus（`simulation/mujoco/` = 物理事实源） | Ambrosia（网页 MuJoCo-WASM 查看器只做展示/回放） | 待建（资产版本号 + 校验和） |

### C1 变更记录（additive-only；老数据零破坏）
- **2026-07-28 · 保留扩展命名空间 `x-<vendor>.*` + 未知键警告 + 扩展登记表（本仓 #69；治 #68 的病因）**：#68 治的是「这一次的病」，本条治**病因**。Iris 四个手部字段能在库里躺半个月没人发现，根因不是 schema 漏了 `additionalProperties: false`，而是**扩展的成本高于隐瞒的成本** —— 采集面要新字段时，选项是「开跨仓契约卡 + 等 canonical 实现 + 等发版」或「直接写，反正 ingest 放行」，后者今天零成本。只要这个梯度在，下一批隐形字段就还会出现，而 canonical 永远最后一个知道。三件事把「扩展」做成一等公民：① **保留命名空间** `x-<vendor>.<field>`（如 `x-iris.hand_left_kpts3d`），`canonical_frame.schema.json` 用 `patternProperties` 显式承认，该前缀下的键**完全静默**；② **扩展登记表** `extensions/registry.json`（+ `registry.schema.json`，root+package 双份），字段 `{name, owner_repo, since, description, promotion_status∈active|proposed|promoted|withdrawn, replaced_by?, reference?, notes?}` —— **登记只需一个本仓 PR，不需要任何跨仓协调、不等发版**，这一条是机制的命门：登记成本必须低于隐瞒成本；③ **警告通道**：`ValidationReport` 新增 `warnings`，`mnesis_canonical.frame_warnings(frame)` 对「非标准键 + 非开放键族（`observation.images.<cam>`）+ 非保留前缀」的键产出 **warning（不是 error）**，CLI 打印且**退出码不变**。**明确不设 `additionalProperties: false`**：会打破 additive 承诺（钉老 schema 版本的消费方因上游加字段变红），且与开放相机键集直接冲突 —— 解法是让越界**可见**，不是让它变成错误。**晋升路径**：登记 → `proposed` → canonical 标准化（走 `type:contract-change`，此时字段形状与在产历史已在桌面上）→ `promoted` + `replaced_by` + 迁移函数 + 弃用窗口。Iris 四个旧名已按 `promoted` 登记为样板（`hand_pose` 的 `replaced_by` 为 `null` —— 它是被**丢弃**式晋升的派生投影）。`SPEC.md` §Extensions + §Conventions / `canonical_frame.schema.json` / `mnesis_canonical.{schema,validate,extension_registry}` / `extensions/` / `tests/test_extensions.py` 同步。**消费方**：无需任何动作（纯 additive，老数据零变红）；新增非标字段时改用 `x-<vendor>.` 前缀并发一个登记 PR。
- **2026-07-27 · 手部关键点 `observation.hand.*`（C11 结案；Parthenon#47 / 本仓 #68；Muso 拍板）**：帧新增 7 个**可选 / additive** 字段，把骨架级手部数据收进单一标准，取代 Iris 私产的 `hand_left_kpts3d` / `hand_right_kpts3d` / `hand_kpts_source` / `hand_pose`。① `observation.hand.left` / `.right`：关节**位置**，展平 `[x,y,z,…]`（米），**变长** —— 长度 = `3 × K`，`K` 由 `observation.hand.layout` 经**骨架登记表**（新增 `skeletons/<id>.json`）解析，与 `embodiment_id` 的 `joint_names` 定义 `observation.state` 长度是同一机制。**不定长 63**：定长会把 MediaPipe 的 21 点拓扑冻进开放标准，而 Eidolon C2（WebXR 25 关节 / OpenXR 26，且带逐关节朝向）与 xMimic 类骨架 retargeting 吃的正是朝向。② `.rot`：关节**朝向**，展平四元数 `{x,y,z,w}`，长度 `4 × K`，仅原生提供朝向的来源填。③ `observation.hand.layout` + `observation.hand.frame`（`world` / `head_anchored` / `hand_local`）—— **有关键点时两者必填**：`frame` 是「2.5D 近似而非真 3D」这条警告的**机器可读形式**，消费方按 `frame == "world"` 过滤，而不是去认某个 source 字符串。④ `observation.hand.source` 只当溯源标签（开放集），不承载几何语义。**手不在场时整键省略**（不发零向量、不许 null）。**`hand_pose`（128 floats）不进 wire**：它是前两者的派生投影，且用标志位 + 补零编码缺席，与本次同时升为铁律的「缺失 = 未知，禁带内哨兵」冲突 —— 归 LeRobot 导出期投影。字段标 **`experimental`**（`SPEC.md` §Versioning 新增字段级 status）：已在产的数据当天进标准，同时保留 stable 前改名的权利。已注册布局：`mediapipe_hand_21`（stable）、`webxr_hand_25` / `openxr_hand_26`（experimental，**待 Eidolon 按真机实现核对**）。`SPEC.md` §Hand keypoints / `canonical_frame.schema.json` / `mnesis_canonical.{schema,validate,skeleton_registry,migrate}` / `skeletons/`（root+package 双份）/ `contracts/canonical_frame_schema_REFERENCE.md` 同步。**消费方对齐**：Iris 按新名改 `CanonicalFrame.toJsonLine`、补 `layout=mediapipe_hand_21` + `frame=head_anchored`、摘掉 `hand_pose`、重新 vendor schema 并从 `contracts.lock` 的 `local_extensions` 摘掉这四个字段；存量数据跑 `python -m mnesis_canonical migrate <data.jsonl> --out <data.jsonl>`。**校验器只认新名，不认双名** —— 标准里的别名从来不会死。
- **2026-07-24 · embodiment registry 增 `capture` 段 + `capture_profiles` 预设（issue #41，Muso 站会直派 2026-07-22）**：embodiment registry（`embodiments/<id>.json` + `embodiment.schema.json`）新增两个**可选/additive**结构，把"换型即配好采集参数"收进契约单一真值——设备端换 embodiment id 即拿到帧率/相机组合/夹爪语义/示教模式/标定要求，无需各消费端硬编码。① `capture`：`default_fps`、`max_duration_s`、`cameras[{name,resolution,fps?}]`、`gripper_capture{mode∈continuous|binary|none, normalized_range?}`（物理行程仍在 `gripper_range`，不在此）、`demonstration_modes⊆{kinesthetic,leader_follower,teleop_only}`（消费端据此切采集 UI）、`calibration{hand_eye_required}`。② `capture_profiles`：命名预设数组 `{name,task?,fps?,cameras?,annotation_template?}`，一机可挂多套。两机型真值：`so_arm101`=leader_follower / front+wrist@640×480 / 30fps / 免手眼标定；`airbot_play`=kinesthetic（重力补偿拖动示教）/ wrist@640×480+front@1280×720 / 30fps / 免手眼标定。**老 registry 条目无这两段仍校验通过**（既有测试零改动）。SPEC.md（§Embodiment registry — capture section，含消费端升版路径）/ `embodiment.schema.json`（root+package 双份同步）/ conformance `tests/test_capture.py` 同步。消费方（Ambrosia 采集/控制台、AIRBOT 采集端）按 additive 惰性接入：换型时读 `capture` 配帧率/相机/时长，按 `gripper_capture.mode` 与 `demonstration_modes` 切 UI，`hand_eye_required` 为真则标定前禁录，`capture_profiles` 按 `name` 供选。
- **2026-07-21 · `action.gripper`（Parthenon#16 问题二 = A，Muso 拍板）**：帧新增可选字段 `action.gripper`，类型 `float`，**归一化 `[0.0, 1.0]`**（`0.0`=完全张开，`1.0`=完全闭合）。字段缺失 = 该数据源不提供夹爪信息（**≠ `0.0`**）；越界/非数值报错，缺失不报错。`action` 向量长度不变（夹爪是独立可选字段，非把 action 扩成 7 维）。物理行程由 embodiment registry 描述，不进逐帧数据。SPEC.md / `canonical_frame.schema.json` / `mnesis_canonical.validate` 同步。消费方（Iris/Eidolon/Daedalus/Ambrosia）按 additive 各自接入，缺失即按无夹爪处理。
- **2026-07-22 · `observation.gripper[.left|.right]`（Parthenon#20 拍板 A，Muso）**：帧新增可选**观测侧**夹爪字段，类型 `float`，**闭合程度归一化 `[0.0, 1.0]`**（`0.0`=完全张开，`1.0`=完全闭合）——**方向与 `action.gripper` 一字不差一致**。`observation.gripper`=单/主夹爪（任意 profile）；`.left` / `.right`=双臂 `robot_v2`。缺失 = 无夹爪观测（**≠ `0.0`**）；越界/非有限报错。语义与 C3 `arms[].gripper` 对齐。SPEC.md / `canonical_frame.schema.json` / `mnesis_canonical.{schema,validate}` / `contracts/canonical_frame_schema_REFERENCE.md` 同步。**背景**：原 PR#39 曾误把观测侧定义为 `0`=闭合（与 `action.gripper` 相反），本次统一改向。

### C3 说明记录（端点补明确 → v1.6 additive 字段新增）
- **2026-07-22 · `arms[].gripper` 端点定义补明确（Parthenon#20 拍板 A，Muso）**：C3 wire 的 `arms[].gripper` 原仅写「夹爪开度 [0.0, 1.0]」**未定义端点**（本次分歧根源）。补明确为「夹爪**闭合程度** [0.0, 1.0]：`0.0` = 完全张开，`1.0` = 完全闭合」，方向与 canonical `action.gripper` / `observation.gripper` 一致。**这是把既有模糊补明确，wire 版本不变（仍 v1.5）**，`XR_ROBOT_CONTRACT.md` / `xr_bridge_SPEC.md` 同步并附消费方核对提示。既有实现（Daedalus xr_bridge / Eidolon / airbot webapp）在此定义明确前可能按相反方向理解，接入前须各自核对——各仓核对属后续独立卡。
- **2026-07-25 · `HandGoal` 新增 confidence/axes/buttons（Daedalus PR#157，Muso 拍板）**：C3 `HandGoal` 新增三个可选字段——`confidence`（float，缺省 1.0，<0.3 视同 `tracking:false` 做安全降级）、`axes`（float 数组，缺省空）、`buttons`（bool 数组，缺省空）。三字段全部可选且向后兼容：不带这些字段的老帧行为完全不变。**动机**：`confidence` 支持渐进降级（追踪中逐步丢失而非二值丢失），`axes`/`buttons` 给 PICO 适配器（#152）映射 XRoboToolkit 全量手柄输入用。本次为 additive 变更，并入 **v1.6**（与同期 PR#39「相机控制协商/视频能力声明」additive 变更同属该 v1.5→v1.6 版本窗口，两者共享同一次 minor 升版，互不冲突）。**两侧测试**：Daedalus 侧 `tests/xr_bridge/test_frame_schema.py` + `test_safety.py`（已随 #157 合并）；Eidolon 侧 webapp `protocol.js` 补发仍在做（#155 T3，标注 pending）。

## 扩展登记（`extensions/registry.json`）—— 非标准字段怎么合法存在

> 来源：本仓 **#69**（Parthenon#47 评审的根因分析）。定义见 `SPEC.md` §Extensions。
> 一句话：**登记的成本必须低于隐瞒的成本**，否则采集面继续偷偷发字段，canonical 永远最后一个知道。

### 什么时候用
你（任一采集面/消费面）需要一个 canonical 还没有的字段时——**不要**先开跨仓契约卡等着，
按下面两步直接上，数据当天就能合法带着这个字段跑。

### 怎么做（两步，只动本仓，不需要跨仓协调）
1. **改名**：把字段写成 `x-<vendor>.<field>`，如 `x-iris.hand_left_kpts3d`。
   该前缀由 `canonical_frame.schema.json` 的 `patternProperties` 显式承认，校验器**完全静默**。
2. **登记**：往 `extensions/registry.json` 加一条，发 PR 到本仓即可——
   **不走 `type:contract-change`、不等 canonical 实现、不等发版**。

```json
{
  "name": "x-iris.hand_left_kpts3d",
  "owner_repo": "Mnesis-Labs/Mnesis-Iris",
  "since": "2026-07-28",
  "description": "左手 3D 关键点，展平 [x,y,z,...]，MediaPipe 21 landmarks。",
  "promotion_status": "active",
  "reference": "Mnesis-Labs/Mnesis-Iris#82"
}
```

`promotion_status`：`active`（在产，暂不申请标准化）· `proposed`（申请升为标准字段）·
`promoted`（已升为标准字段，`replaced_by` 指向新名，进入弃用窗口）· `withdrawn`（已停产）。

### 不登记会怎样
不会红。校验器对「非标准 + 非开放键族 + 非保留前缀」的键产出 **warning**，
`python -m mnesis_canonical validate` 会打印，但**退出码不变**、ingest 不拒。
**这是刻意的**：设 `additionalProperties: false` 会打破 additive 承诺（钉老 schema
版本的消费方，会因为上游加了新字段而变红），且与开放的 `observation.images.<cam>`
键集直接冲突。要的是**越界可见**，不是越界变红。

### 晋升为标准字段
`proposed` → canonical 走 `type:contract-change` 标准化 → `promoted` + `replaced_by`
+ 迁移函数（`mnesis_canonical.migrate`）+ 弃用窗口（期间旧名只 warning）。
canonical 由此拿到一份「**什么即将变成标准**」的早期预警名单
（`list_extensions(promotion_status="proposed")`），而不是半个月后靠一次全仓评估发现。

## C2 幂等语义（重复上传去重）

> 来源：**Parthenon#18**（Muso 拍板方案 A）。依据：Ambrosia main `app/main.py:825-826` 的 dedup 实现。这是把既有行为写成文，不是变更契约；三个采集面（Iris 手机 / Daedalus 机器人 / Eidolon Quest）统一参照。

服务端去重键的构造（Ambrosia `app/main.py:825-826`）：

```python
dedup_key = f"{episode_index}|{device}|{hashlib.sha256(jsonl_bytes).hexdigest()}"
content_hash = hashlib.sha256(dedup_key.encode()).hexdigest()
```

1. **幂等键 = 内容哈希**：由 `episode_index | source.device | sha256(data.jsonl 字节)` 三元组构成。重复 POST **同一内容** → 返回**同一 episode id**，库中只存一条。
2. **不是 header 幂等**：服务端**不消费 `Idempotency-Key` 请求头**。客户端发不发该头都不影响去重结果——去重完全由上述内容哈希决定。
3. **客户端约束（关键）**：**重试必须复用同一份已序列化的字节，不得重新打包**。若重试前重新生成 `data.jsonl`（时间戳 / 字段序变化）或重新压缩，`sha256(jsonl_bytes)` 即变，服务端会把它当作**新 episode** 入库，产生重复。
4. **实践指引**：客户端应在**首次序列化后缓存字节**，整个重试链路复用该缓存，而不是每次从源数据重新构建。这样才能保证网络抖动 / 超时重试下的端到端幂等。

## D-18 契约 vNext 落地（第五批 · C8 夹爪 + 相机控制协商 + 视频能力声明）

> 来源：mnesis-canonical#38（D-18 / 4a S21）。三件全部 **additive**，v1.3/v0.3 既有测试零改动全绿。canonical lane 先做本张。

三处补齐：
1. **C8 夹爪通道**（帧侧，C1）：canonical 帧新增可选 `observation.gripper` / `observation.gripper.left` / `observation.gripper.right`，连续量 `[0,1]`（0=闭合，1=张开），语义对齐 C3 `arms[].gripper`。定义见 `SPEC.md` §Gripper channel + `contracts/canonical_frame_schema_REFERENCE.md`。**原 C8「夹爪/末端执行通道」议题**（登记于本文 Tech Lead 提案区，单独立卡 #31）在此落地帧侧表示。
2. **相机控制协商**（线侧，C3 → v1.6）：新增 `C3_CameraControl`（头显 → 机器，`{camera_id,width,height,fps,bitrate,codec}`）+ `C3_CameraStatus`（机器 → VR，实际生效参数）。语义对齐业界 `OPEN_CAMERA` 式协议，走既有 WS 信封。
3. **视频传输能力声明**（线侧，C3 → v1.6）：`C3_Info.video_capabilities`（`transports: webrtc|mjpeg` 等），为已拍板 WebRTC 线（[DQ-1]）预留，消费端 YC 后接入。

### 消费端 `contracts.lock` 升版路径（各消费方对齐步骤）

canonical 侧 `contracts/contracts.lock` 已随本次改动重算（`XR_ROBOT_CONTRACT.md`、`xr_bridge_SPEC.md`、`canonical_frame_schema_REFERENCE.md` 三文件哈希更新）。各仓持有 C3 镜像 / C1 校验的消费方按下述升版：

- **Daedalus**（C3 Owner，xr_bridge 服务端）：将 `docs/integration/XR_ROBOT_CONTRACT.md` 镜像同步到 v1.6；在 `C3_Info` 增发 `video_capabilities`；实现 `C3_CameraControl` 接收 + `C3_CameraStatus` 应答（clamp 到硬件能力）。harness 增加相机协商用例。**旧客户端零改动**：未实现方忽略新消息即可。
- **Eidolon**（C3 消费方，Quest 前端）：升到 v1.6 后可读 `video_capabilities` 选择视频线、下发 `C3_CameraControl`；未升版时忽略新消息，遥操作核心不受影响。采 gripper 时按 `observation.gripper*` 写入 canonical 帧。
- **airbot 仓 / Daedalus（C1 消费方，机器人采集面）**：`observation.gripper*` 为可选 additive——升 `mnesis-canonical` 版本后即可产出/校验带夹爪的帧；不升版的旧数据仍全绿。
- **Ambrosia**（C1 消费方，ingest）：升 `mnesis-canonical` 依赖版本，ingest 校验自动接受 `observation.gripper*`（可选，范围 `[0,1]`）；无需改 schema 门。WebRTC 线 YC 后按 `video_capabilities` 接入。

升版校验：`python -m mnesis_canonical.contracts_check`（哈希一致）+ `pytest -q`（既有测试零改动全绿）。

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

### C8(新草案)· `space_id` 跨引擎同空间对齐(来源:Eidolon TL IR-a · Iris TL 背书)
现状 `spatial_anchor_id` 是各引擎私有 id(Iris=ARCore anchor、Eidolon=OpenXR anchor),**两命名空间不可关联,同房间的手机面+Quest 面数据 merge 不了**。建议 canonical 加 `space_id`(房间 UUID 或共享 fiducial 原点标识)+ 约定 anchor 位姿表示为**在该 space 系下**的 SE(3)。**这是 Ambrosia「同空间多面视图」/多视角 4DGS 的钥匙**。消费方=Iris·Eidolon·Ambrosia。

### C9(新草案)· `camera_intrinsics` 一等字段(来源:Eidolon TL IR-b · Iris TL 背书)
相机内参(fx,fy,cx,cy,畸变,分辨率)应是 **canonical 一等字段**,不塞各仓私有 sidecar。两采集面同表示后,**4DGS/重构才能同吃手机+Quest 帧**。Owner=canonical 定义;消费方=Iris·Eidolon 产出、Ambrosia/重构消费。

> **C8-C11 编号说明**：Eidolon/Tech-Lead 2026-07-10 曾在 PR#2 提出 C8-C11 四项跨仓建议，但 main 上 C8 已分配给 `space_id`、C9 已分配给 `camera_intrinsics`(后者主题已采纳落地)，造成编号撞车 → PR#2 长期 CONFLICTING。Muso 拍板（Parthenon#16 问题一 = A）关闭 PR#2，其中仍有效两项以新编号 **C10 / C11** 重新登记(见下)；原 C8「夹爪/末端执行通道」已单独立卡 mnesis-canonical#31。以下两条**仅为草案登记，待 Muso 拍板，不视为已生效契约**。

### C10(新草案)· Isaac 三 open item 冻结截止日(来源:Eidolon TL 2026-07-10;原 PR#2 重登记)
现状:canonical↔Isaac/GR00T 三处坐标/旋转表示悬而未决(`SPEC.md` §Compatibility 已标 ⚠️),需一个**冻结截止日**避免长期悬空:
1. **四元数序**:wire 用 `xyzw`,Isaac 原生 `wxyz`。
2. **世界系 up-axis 与手性**:Eidolon 为 Unity 左手系,发帧前必须知道目标系(Y-up / 右手 vs 左手)。
3. **action 旋转表示**:canonical 为 axis-angle (rad),Isaac/GR00T 期望待确认。
TL 建议裁决方向(**方向为建议,待 Muso 拍板,勿写成已决**):wire 保持 `xyzw` / Y-up,Isaac 侧走 adapter 转换,并给三项定一个决策日期。Owner=canonical 定义;消费方=Eidolon·Daedalus(Isaac/GR00T 侧)。**状态:草案/待拍板。**

### C11 · `hand_skeleton` / body-pose 可选字段(来源:Eidolon TL 2026-07-10;原 PR#2 重登记;xMimic 门槛日 2026-07-31)
原始现状:Eidolon 只采 `head_pose` + `action`,无骨架;xMimic 类工作需要**骨架级 teleop 数据**。要点:该由 **canonical 统一定义**,而非各采集面私造;且**决策优先于实现**。Owner=canonical 定义;消费方=Eidolon 产出、Ambrosia/训练消费。

**状态：手部一半已结案（2026-07-27，Muso 拍板 · Parthenon#47 / 本仓 #68）**，落成 `observation.hand.*` 七字段 + `skeletons/` 骨架登记表，见上方 C1 变更记录。触发点是 Iris 已在产四个非标字段而 Eidolon C2 即将产同类数据 —— 正是本条草案预判的场景。

**body-pose 一半仍为草案**：机制已经现成 —— `skeletons/` 的 `kind` 字段已预留 `"body"`，一个 body 布局（如 SMPL 系）加进登记表即可复用同一套变长向量 + layout id + 参考系的校验；剩下要拍的只是布局选型与是否需要独立的 `observation.body.*` 键。**待 Eidolon/训练侧提出真实需求再立卡。**

## B. 各仓产品建议(对应仓自行排期,非契约)

| 仓 | 建议 | 为什么(飞轮/商业价值) |
|---|---|---|
| **Ambrosia** | **① 数据集"价值分"**:Themis 质量 → 每数据集一个可解释评分,直接当**对外定价信号**。② **覆盖缺口分析**:控制台告诉你"缺什么数据"(按任务/物体/光照/设备分布)→ 指挥下一步采集,这是飞轮的大脑。③ **回放即评测**:用 MuJoCo 回放算"录制动作是否物理可行/自洽"→ 自动质量门(物理对齐=护城河)。④ **PII 脱敏层**:ego 相机拍到人脸/屏幕/证件,卖数据前的脱敏+同意 = 法律必需 + 差异化。 | 把"质量"接到"商业化"与"采集指挥",而不止是存储看板 |
| **Daedalus** | **① 时间同步(见 C6)** 机器人端记录 `clock_offset_ns`。② **T3 上传带 `frames.zip`**(现在只 manifest+jsonl):机器人前视/腕视图打包,平台回放才有画面。③ **C5 MJCF 发版**:给模型加 `version+sha256` 发布,让 Ambrosia 忠实回放(S6-2 依赖)。 | 让机器人 episode 在平台"可回放、可对齐、有画面" |
| **Eidolon** | **① MI-1 Quest→Canonical 导出器 = 三采集面里唯一还缺的一面**,优先级应最高(手机✅/机器人✅ 都通了)。② 遥操作 episode 带手部/头显位姿 → `source.device=quest`,直接喂飞轮。 | 补齐第三条数据流,飞轮才"三面齐" |
| **Iris** | 见本仓 `docs/ROADMAP_IRIS.md`(GL 流畅度→溯源字段→离线可靠投递→端上回看→AR 眼镜形态)。 | — |

## C. 关键洞察:飞轮的"三面齐"已在临界点
手机(Iris)✅ 真机验过 · 机器人(Daedalus T3)✅ 上传器已做 · Quest(Eidolon MI-1)⛔ 唯一缺口。**建议把 Eidolon MI-1 + Ambrosia S6(收 3 面 + 忠实回放)+ Daedalus C5 发版 作为下一个跨仓"会师点"**,一次联测三面同屏 = 可对投资人演示的"真实数据飞轮"。

---

# Tech Lead 复盘 + 新增建议(2026-07-10 晚)— 各仓自行决策

> 依据:本轮各仓夜班后的实地巡查 + Ambrosia 首次真机联通。仍是**建议**,勿越权代改。

## D. 状态刷新(飞轮体检)

| 采集面 | 仓 | 到平台的链路 | 状态 |
|---|---|---|---|
| 手机 ego | Iris | `POST /api/episodes`(manifest+jsonl+**MP4 video** N4) | ✅ 真机验过 |
| 机器人 robot_replay | Daedalus | `xr_bridge/mnesis_export.py` → `/api/episodes` | ✅ 上传器已做;⚠️ **仍缺 frames.zip**(回放无画面) |
| Quest 遥操作/ego | Eidolon | MI-1 Canonical 导出器 + MI-2 上传 | ⛔ **唯一缺口**(xr_bridge C3 已合规,但采集面到平台的 MI-1/MI-2 未做) |

- **Ambrosia**:S5 加固完成(**129 tests 绿**,Tech Lead 独立复跑;无测试被删);Cline 已起草 T1 路线图 + S6。**真机首次联通**:两只 SO-ARM101 主臂(COM3/COM4)经 `app/hw.py` RealDriver 读到物理正确的关节角(肩抬≈-1.7 / 肘≈+1.57 = home 位),tick→rad 换算经真机验证。
- **判断**:飞轮"三面齐"卡在 **Eidolon MI-1**。这条不通,S6"收三面真实入库"就只有两面。**建议把 Eidolon MI-1 提到全网最高优先级。**

## E. 新增战略建议(超出已列的,给各仓参考)

### E1 · Sim2real 差距度量 = Ambrosia 独有护城河(强烈建议 Ambrosia 排期)
Ambrosia 是全网**唯一同时握有**「真实 episode + 真机 MJCF(C5)+ 浏览器回放」的地方。据此可对每条 robot_replay episode 算一个 **sim2real 差距分**:把录制的 `action` 在 MuJoCo 里前向执行,与录制的 `observation.state` 逐帧比对(位姿残差/能量/是否穿模)。产出:①每条数据的"物理自洽度"自动质量门(脏数据——跳变/丢跟踪/非物理——自动降级);②对外可售的"物理已验证"质量档;③训练前就知道哪些 demo 值得学。竞品(Scale/光轮)给的是**未验证**数据。这比单纯 Themis 规则门高一个维度。

### E2 · Teleop = 免费的完美标注工厂(建议 Ambrosia + Daedalus 共识)
主臂→从臂遥操作,人手演示**天然产出高质量 action 标签**(不用事后标注)。建议把"遥操作录制"做成平台的**默认数据生产回路**,不只是一个演示页:每段遥操作 = 一条带完美 action 的 robot_replay episode。配合 E1 的物理门,这是**最便宜的高质量具身数据来源**。Daedalus 侧把 `mnesis_export` 的录制做成"一键录 30s→自动上传",Ambrosia 侧把 teleop 页的录制计数/质量即时反馈做足。

### E3 · 数据血缘 = 可审计 = 可卖(建议 canonical + Ambrosia)
在 C1-vNext 溯源之上再进一步:每条数据从原始采集到成品数据集的**每一步变换**(标注/去重/质量门/脱敏)都记一条血缘(who/when/what/version)。买家买的是**信任**——"这个数据集 = 这些原始采集 + 这些处理步,可审计"。这是把数据从"字节"变成"可溢价商品"的关键,Neuracore/Scale 在具身数据上都没做透。Ambrosia 落地成本低(数据集对象上挂一个 lineage 列表),但商业价值高。

## F. 各仓下一步优先级(建议,自行排期)

- **Eidolon** ⇒ **MI-1 Quest→Canonical 导出器**(最高优先,补齐第三面)。手部/头显位姿→`head_pose_SE3`,`source.device=quest`;录一段遥操作→平台出 `quest` 卡。这条是全网飞轮闭环的最后一块。
- **Daedalus** ⇒ ① `mnesis_export` 加 **frames.zip**(前视/腕视,C2a `%06d.jpg`),否则平台回放无画面;② **C5 MJCF 发版**(`@version + sha256`),Ambrosia S6-2 忠实回放依赖它;③(可选)`clock_offset_ns`(C6)。
- **Iris** ⇒ 已很成熟;建议补 **C1-vNext 溯源字段**(manifest 层 `schema_version/capture_app/app_version/git_sha/device_id/session_id`),为"可售数据"打底。
- **canonical(本仓)** ⇒ 把 **C1-vNext 溯源** + **C6 时间同步** 从提案定为 v1(定字段),给各端对齐目标;C5/C4 待 Daedalus 定义后登记。

## G. 建议的下一个跨仓"会师点"(投资人可演示)
Eidolon MI-1 ✅ + Ambrosia S6(收 3 面 + robot 忠实回放 + LeRobot 导出)✅ + Daedalus(frames.zip + C5 发版)✅ → **一次联测:手机/Quest/机器人三面同屏入库 → 数据集 → 忠实回放 → 一键导出 LeRobot**。这就是"真实数据飞轮"的可演示形态,也是融资 Demo 的核心画面。
