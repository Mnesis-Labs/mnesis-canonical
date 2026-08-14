# Mnesis 跨仓契约登记簿（CONTRACTS.md）

> **规则**：任何跨仓接口，先在这里登记/改版本，再改代码；两侧仓库各自持有钉死该契约的测试。改契约的 PR 必须在描述里链接两侧测试。本文件由 Tech Lead（Claude Code）守门。
> 仓库：**Iris**=手机采集 · **Eidolon**=Quest VR 前端 · **Daedalus**=机器人执行/训练 · **Ambrosia**=数据平台/控制台 · **canonical**=本仓（数据标准）。

| # | 契约 | 版本 | Owner（定义方） | 消费方 | 两侧测试 |
|---|---|---|---|---|---|
| C1 | **Canonical Frame Schema**（JSONL 帧格式：字段/向量长/双时间戳/词表） | v0.1 | canonical（`SPEC.md` + `canonical_frame.schema.json`） | Iris·Eidolon·Daedalus·Ambrosia | canonical `tests/` · Iris `CanonicalSchemaContractTest` · Ambrosia ingest 校验 |
| C2 | **Episodes Ingest HTTP**（`POST /api/episodes` multipart：`manifest`+`jsonl`+`video?`+`frames?`；`X-App-Token?`） | v1.1 | Ambrosia（`docs/SPRINT_S4_CLINE.md` 契约节 + `docs/HANDOFF_S4.md`） | Iris·Eidolon·Daedalus | Ambrosia `tests/test_iris_contract.py`（Ct-1..11） · Iris `EpisodeUploaderHeaderTest`+S4 D2 |
| C2a | frames.zip 规范：根目录 `%06d.jpg`（与 `frame_index` 对齐，1fps）；包≤200MB/帧≤5MB/≤3600 帧。服务端宽容收 png/jpg/jpeg/webp/bmp，规范名以 jpg 为准 | v1.1 | Ambrosia | Iris（Eidolon/Daedalus 后续） | 同上 |
| C3 | **xr_bridge WS**（VR↔机器人实时遥操作：帧协议/急停闩锁/重连再锚定/看门狗/双臂数组信封/PlanGate/相机控制协商/视频能力声明/WebRTC 信令） | v1.7 | Daedalus（`docs/integration/XR_ROBOT_CONTRACT.md`） | Eidolon | Daedalus harness + 坐标真值 fixture · Eidolon PH-2/PH-3 测试 |
| C4 | **Robot-Bridge API**（平台↔真机：关节读写/示教/安全），目的=把硬件控制留在 Daedalus、Ambrosia 只经 API 消费 | **草案 TBD** | Daedalus（待定义） | Ambrosia（`bridge/hw_bridge.py` 现状=临时直连，待迁移到本契约） | 待建 |
| C5 | **MJCF 仿真资产**（机器人/场景模型单一事实源） | **草案 TBD** | Daedalus（`simulation/mujoco/` = 物理事实源） | Ambrosia（网页 MuJoCo-WASM 查看器只做展示/回放） | 待建（资产版本号 + 校验和） |
| C9 | ** 一等字段**（相机内参：fx/fy/cx/cy + 畸变模型枚举，放 embodiment registry ；模型必须含鱼眼——pinhole 系在 200°FOV 发散） | v1 | canonical（ §Camera intrinsics + ） | Iris·Eidolon 产出 · Ambrosia/重构消费 · 龙旗 DatCap | canonical  · Iris/Eidolon 产出端自校验 |
| C9 | **`camera_intrinsics` 一等字段**（相机内参：fx/fy/cx/cy + 畸变模型枚举，放 embodiment registry `capture.cameras[].intrinsics`；模型必须含鱼眼——pinhole 系在 200°FOV 发散） | v1 | canonical（`SPEC.md` §Camera intrinsics + `embodiments/embodiment.schema.json`） | Iris·Eidolon 产出 · Ambrosia/重构消费 · 龙旗 DatCap | canonical `tests/test_camera_intrinsics.py` · Iris/Eidolon 产出端自校验 |
| C12 | **双端语义契约 PS0**（`ObservationLabel` / `scene_graph` + 三个 8442 WS 消息 `semantic_label` / `scene_graph` / `colocalization`；`class_id` 取值域 = `taxonomies/object_class_v1.json`） | v1 | canonical（`SPEC.md` §Dual-endpoint semantic perception + `mnesis_canonical/semantic.schema.json`） | Daedalus（融合，ADR-004）·Eidolon（头显消费） | canonical `tests/test_semantic.py` + `examples/semantic/` golden · Daedalus PS1/PS2a/PS3 · Eidolon PS2b |

### C1 变更记录（additive-only；老数据零破坏）
- **2026-07-28 · 升两条通则：「缺失 = 未知，禁带内哨兵」+ 字段级 status（issue #70；来源 Parthenon#47 评审）**：两条都是本仓已临时拍过、但从未升成通则的规范，此前每加一个字段都要重新吵一遍。① 升 `SPEC.md` §Conventions 为铁律：「缺失 = 未知，禁带内哨兵」—— 任何情况下不得用 `0`、零向量、`-1`、`NaN`、`""`、存在标志位等带内哨兵值编码「未知/不适用」，不知道就省略该键；消费方 MUST NOT 给缺失可选字段填默认值。回指两次既有拍板：2026-07-21 `action.gripper` 缺失 ≠ `0.0`、2026-07-27 `spatial_anchor_pose_SE3` 缺失 ⇒ 跳过一致性校验（不回退 `head_pose_SE3`），并自动出局 #47 里 `hand_pose`（标志位 + 63 个零）一类带内哨兵方案。② 升字段级 `status`（`experimental` / `stable` / `deprecated`）为 `SPEC.md` §Versioning 正式定义：`experimental` = 已收编可产可校验但 stable 前可改名/改形、不算破坏性；`stable` = 冻结、仅 additive、改名需 major；`deprecated` = 将移除、须附 `deprecated_since` + 迁移指引。`canonical_frame.schema.json` 每个 property 标 `x-status`（现有字段一律 `stable`，`observation.hand.*` 七字段标 `experimental`），`SPEC.md` 字段表加 Status 列并删除一份重复的「C8」夹爪行。③ `mnesis_canonical.schema` 新增 `FIELD_STATUS` + `EXPERIMENTAL_KEYS` 常量；`validate.{validate_frame,validate_frames}` 新增 `strict_stable` 参数、CLI `validate --strict-stable` 拒收含 experimental 字段的帧（下游「只吃冻结字段」的开关）。**老数据零破坏**：`strict_stable` 默认关闭，不加 flag 时 experimental 字段照常校验通过。SPEC.md / `canonical_frame.schema.json` / `mnesis_canonical.{schema,validate,__main__}` 同步。
- **2026-07-27 · 手部关键点 `observation.hand.*`（C11 结案；Parthenon#47 / 本仓 #68；Muso 拍板）**：帧新增 7 个**可选 / additive** 字段，把骨架级手部数据收进单一标准，取代 Iris 私产的 `hand_left_kpts3d` / `hand_right_kpts3d` / `hand_kpts_source` / `hand_pose`。① `observation.hand.left` / `.right`：关节**位置**，展平 `[x,y,z,…]`（米），**变长** —— 长度 = `3 × K`，`K` 由 `observation.hand.layout` 经**骨架登记表**（新增 `skeletons/<id>.json`）解析，与 `embodiment_id` 的 `joint_names` 定义 `observation.state` 长度是同一机制。**不定长 63**：定长会把 MediaPipe 的 21 点拓扑冻进开放标准，而 Eidolon C2（WebXR 25 关节 / OpenXR 26，且带逐关节朝向）与 xMimic 类骨架 retargeting 吃的正是朝向。② `.rot`：关节**朝向**，展平四元数 `{x,y,z,w}`，长度 `4 × K`，仅原生提供朝向的来源填。③ `observation.hand.layout` + `observation.hand.frame`（`world` / `head_anchored` / `hand_local`）—— **有关键点时两者必填**：`frame` 是「2.5D 近似而非真 3D」这条警告的**机器可读形式**，消费方按 `frame == "world"` 过滤，而不是去认某个 source 字符串。④ `observation.hand.source` 只当溯源标签（开放集），不承载几何语义。**手不在场时整键省略**（不发零向量、不许 null）。**`hand_pose`（128 floats）不进 wire**：它是前两者的派生投影，且用标志位 + 补零编码缺席，与本次同时升为铁律的「缺失 = 未知，禁带内哨兵」冲突 —— 归 LeRobot 导出期投影。字段标 **`experimental`**（`SPEC.md` §Versioning 新增字段级 status）：已在产的数据当天进标准，同时保留 stable 前改名的权利。已注册布局：`mediapipe_hand_21`（stable）、`webxr_hand_25` / `openxr_hand_26`（experimental，**待 Eidolon 按真机实现核对**）。`SPEC.md` §Hand keypoints / `canonical_frame.schema.json` / `mnesis_canonical.{schema,validate,skeleton_registry,migrate}` / `skeletons/`（root+package 双份）/ `contracts/canonical_frame_schema_REFERENCE.md` 同步。**消费方对齐**：Iris 按新名改 `CanonicalFrame.toJsonLine`、补 `layout=mediapipe_hand_21` + `frame=head_anchored`、摘掉 `hand_pose`、重新 vendor schema 并从 `contracts.lock` 的 `local_extensions` 摘掉这四个字段；存量数据跑 `python -m mnesis_canonical migrate <data.jsonl> --out <data.jsonl>`。**校验器只认新名，不认双名** —— 标准里的别名从来不会死。
- **2026-07-24 · embodiment registry 增 `capture` 段 + `capture_profiles` 预设（issue #41，Muso 站会直派 2026-07-22）**：embodiment registry（`embodiments/<id>.json` + `embodiment.schema.json`）新增两个**可选/additive**结构，把"换型即配好采集参数"收进契约单一真值——设备端换 embodiment id 即拿到帧率/相机组合/夹爪语义/示教模式/标定要求，无需各消费端硬编码。① `capture`：`default_fps`、`max_duration_s`、`cameras[{name,resolution,fps?}]`、`gripper_capture{mode∈continuous|binary|none, normalized_range?}`（物理行程仍在 `gripper_range`，不在此）、`demonstration_modes⊆{kinesthetic,leader_follower,teleop_only}`（消费端据此切采集 UI）、`calibration{hand_eye_required}`。② `capture_profiles`：命名预设数组 `{name,task?,fps?,cameras?,annotation_template?}`，一机可挂多套。两机型真值：`so_arm101`=leader_follower / front+wrist@640×480 / 30fps / 免手眼标定；`airbot_play`=kinesthetic（重力补偿拖动示教）/ wrist@640×480+front@1280×720 / 30fps / 免手眼标定。**老 registry 条目无这两段仍校验通过**（既有测试零改动）。SPEC.md（§Embodiment registry — capture section，含消费端升版路径）/ `embodiment.schema.json`（root+package 双份同步）/ conformance `tests/test_capture.py` 同步。消费方（Ambrosia 采集/控制台、AIRBOT 采集端）按 additive 惰性接入：换型时读 `capture` 配帧率/相机/时长，按 `gripper_capture.mode` 与 `demonstration_modes` 切 UI，`hand_eye_required` 为真则标定前禁录，`capture_profiles` 按 `name` 供选。
- **2026-07-21 · `action.gripper`（Parthenon#16 问题二 = A，Muso 拍板）**：帧新增可选字段 `action.gripper`，类型 `float`，**归一化 `[0.0, 1.0]`**（`0.0`=完全张开，`1.0`=完全闭合）。字段缺失 = 该数据源不提供夹爪信息（**≠ `0.0`**）；越界/非数值报错，缺失不报错。`action` 向量长度不变（夹爪是独立可选字段，非把 action 扩成 7 维）。物理行程由 embodiment registry 描述，不进逐帧数据。SPEC.md / `canonical_frame.schema.json` / `mnesis_canonical.validate` 同步。消费方（Iris/Eidolon/Daedalus/Ambrosia）按 additive 各自接入，缺失即按无夹爪处理。
- **2026-07-22 · `observation.gripper[.left|.right]`（Parthenon#20 拍板 A，Muso）**：帧新增可选**观测侧**夹爪字段，类型 `float`，**闭合程度归一化 `[0.0, 1.0]`**（`0.0`=完全张开，`1.0`=完全闭合）——**方向与 `action.gripper` 一字不差一致**。`observation.gripper`=单/主夹爪（任意 profile）；`.left` / `.right`=双臂 `robot_v2`。缺失 = 无夹爪观测（**≠ `0.0`**）；越界/非有限报错。语义与 C3 `arms[].gripper` 对齐。SPEC.md / `canonical_frame.schema.json` / `mnesis_canonical.{schema,validate}` / `contracts/canonical_frame_schema_REFERENCE.md` 同步。**背景**：原 PR#39 曾误把观测侧定义为 `0`=闭合（与 `action.gripper` 相反），本次统一改向。

### C9 变更记录（additive-only；老数据零破坏）
- **2026-08-14 · `camera_intrinsics` 一等字段转正（issue #117；来源 龙旗 DatCap 3 路鱼眼 200° 需求）**：C9 从草案转正为 v1，相机内参作为 embodiment registry `capture.cameras[].intrinsics` 内的可选结构。定义畸变模型枚举（`pinhole` / `pinhole_radtan` / `kannala_brandt` / `double_sphere`），确保鱼眼 200° 视场使用正确模型（pinhole+radtan 在 180° 附近发散）。内参是设备/标定属性，不是逐帧属性——放 embodiment registry 不涨每帧体积。`SPEC.md` §Camera intrinsics / `embodiments/embodiment.schema.json`（root+package 双份同步）/ `mnesis_canonical.schema` 新增 `CAMERA_MODELS` / conformance `tests/test_camera_intrinsics.py` / `contracts/canonical_frame_schema_REFERENCE.md` 同步。**老数据零破坏**：`intrinsics` 为可选字段，现有 embodiment 条目无此段仍校验通过。

### C3 说明记录（端点补明确 → v1.6 additive 字段新增 → v1.7 WebRTC 信令 additive）
- **2026-07-28 · WebRTC 信令三消息（issue #60，C1 架构拍板后落卡）**：C3 v1.7 新增三条 WebRTC 信令消息——`video_offer`（消费端 → 机器人侧，SDP offer）、`video_answer`（机器人侧 → 消费端，SDP answer）、`video_ice`（双向，ICE candidate 交换）。**多订阅者字段**：`stream_id`（目标视频流标识）+ `subscriber_id`（订阅者标识）——机器人侧通过此字段区分「这条 answer 是回给 Web 还是回给 Quest」。**QoS 提示**：`qos_hint`（可选枚举，`low_latency` / `stable`），各订阅者 ABR/缓冲策略凭此区分，编码侧一路编码不分裂。**V2 预留**：`codec` / `width` / `height` 字段已定义但暂不实现 360° 全景。**additive 声明**：≤v1.6 客户端忽略三消息，视频退回到 MJPEG 线，遥操作核心功能零破坏。**JSON Schema**：`contracts/webrtc_signaling.schema.json` 附正例+反例测试。**消费方升版路径**：见本节末。**两侧测试**：Daedalus 侧 harness 需新增 `video_offer`/`video_answer`/`video_ice` 信令回合；Eidolon 侧 webapp `protocol.js` 需新增三条消息处理。
- **2026-07-22 · `arms[].gripper` 端点定义补明确（Parthenon#20 拍板 A，Muso）**：C3 wire 的 `arms[].gripper` 原仅写「夹爪开度 [0.0, 1.0]」**未定义端点**（本次分歧根源）。补明确为「夹爪**闭合程度** [0.0, 1.0]：`0.0` = 完全张开，`1.0` = 完全闭合」，方向与 canonical `action.gripper` / `observation.gripper` 一致。**这是把既有模糊补明确，wire 版本不变（仍 v1.5）**，`XR_ROBOT_CONTRACT.md` / `xr_bridge_SPEC.md` 同步并附消费方核对提示。既有实现（Daedalus xr_bridge / Eidolon / airbot webapp）在此定义明确前可能按相反方向理解，接入前须各自核对——各仓核对属后续独立卡。
- **2026-07-25 · `HandGoal` 新增 confidence/axes/buttons（Daedalus PR#157，Muso 拍板）**：C3 `HandGoal` 新增三个可选字段——`confidence`（float，缺省 1.0，<0.3 视同 `tracking:false` 做安全降级）、`axes`（float 数组，缺省空）、`buttons`（bool 数组，缺省空）。三字段全部可选且向后兼容：不带这些字段的老帧行为完全不变。**动机**：`confidence` 支持渐进降级（追踪中逐步丢失而非二值丢失），`axes`/`buttons` 给 PICO 适配器（#152）映射 XRoboToolkit 全量手柄输入用。本次为 additive 变更，并入 **v1.6**（与同期 PR#39「相机控制协商/视频能力声明」additive 变更同属该 v1.5→v1.6 版本窗口，两者共享同一次 minor 升版，互不冲突）。**两侧测试**：Daedalus 侧 `tests/xr_bridge/test_frame_schema.py` + `test_safety.py`（已随 #157 合并）；Eidolon 侧 webapp `protocol.js` 补发仍在做（#155 T3，标注 pending）。

## C12 双端语义契约（PS0 · 契约先行 · canonical 定义，两端只读消费）

> 来源：Muso 2026-07-28 拍板新增 **PS 轨（双端识别与共定位）**。设计全文 Parthenon `research/25-dual-endpoint-perception-and-colocalization_2026-07-28.md`（Parthenon#58）；决策落点 Daedalus ADR-004（Daedalus#238）；排期 Parthenon `ROADMAP.md` T2-percep。本仓 issue #77。
> **契约先行的理由**：机器人端（Daedalus）与头显端（Eidolon）产出的是**同一种东西**。两端各自定义 schema，融合器第一天就要写适配层，`class_id` 立刻漂移。照 C1 视频信令先例：canonical 先行，两端只读消费。
> **边界**：本仓**只定契约不写实现**。融合逻辑归 Daedalus（ADR-004），头显侧消费归 Eidolon。

**定稿件**：`SPEC.md` §Dual-endpoint semantic perception（权威定义）· `mnesis_canonical/semantic.schema.json`（JSON Schema，供非 Python 端校验）· `mnesis_canonical/semantic.py`（参考校验器）· `taxonomies/object_class_v1.json` + `taxonomy.schema.json` + `mnesis_canonical/taxonomy_registry.py`（`class_id` 取值域）· `examples/semantic/`（golden 样本）· `tests/test_semantic.py`（本侧测试）。

三层，故意分开：**`ObservationLabel`**（某一端的单次观测，本身不权威）→ **`scene_graph`**（融合产物，机器人端权威，label = ObservationLabel + `state`/`witnesses`/`dispute`）→ **三个 8442 消息**（信封 v1 = C3 公共头 `{type,seq,ts,body}` 原样，因为与 30 Hz teleop 共用同一条 socket）。

### 本仓定稿对草案的三处收紧（以本仓定稿为准）

1. **时间戳统一纳秒整数**：草案的 `observed_at`（浮点秒）定为 **`observed_at_ns`（int64 Unix 纳秒）**。标准里已有且仅有一种时间单位——`t_ns` / `t_hw_ns` / `events.jsonl` 的 `t_ns` / C3 信封 `ts` 全是整数纳秒；一个 wire 格式里放两种单位，边界转换出 bug 只是时间问题。单位写进字段名。同理 `updated_at_ns` / `computed_at_ns`。PS0 是 PS 轨第一张卡、两端尚无实现，此时统一成本最低。
2. **`frame_id` 收成闭集 `{map}`**：草案写「必须是共同参考系，不接受局部系」，本仓把它变成**可校验事实**——`cam_overhead` / `headset` / `base_link` 一律拒收。头显端先用 `colocalization` 外参把点变换到 `map` 再发；不可融合的标签宁可被拒，不可被静默错融。
3. **`confidence` 必填**：没写置信度的输入没法参与融合。人裁决标签填 `1.0`。

### 关键设计（消费方按此实现，勿自行发挥）

- **`source` 枚举第一天就含 `headset` / `human`**，尽管头显侧识别（PS4）与人裁决尚在 backlog。后补枚举值是契约变更，每个硬编码二值分支的消费方都得回头改一遍；现在加进去零成本。**上行 `semantic_label` 只收 `headset` / `human`**——`robot` 标签本来就在权威侧，不上行。
- **`class_id` 取值域 = `taxonomies/object_class_v1.json`，消费方不得自造**。经**分类登记表**（`mnesis_canonical.taxonomy_registry`）解析，与 `skeletons/` 定义 `observation.hand.layout`、`embodiments/` 定义 `observation.state` 是同一机制——标准里只保留一种「取值域在别处声明」的做法。缺类别 = 对该文件开 PR。`unknown` 是「几何观测到了但类别未定」的**真实观测**，不是缺登记项的兜底。JSON Schema 内的 enum 由该文件生成，`tests/test_semantic.py` 钉死两者一致（头显端用 JS 校 schema，漂移即两端松紧不一）。
- **`stale` 标签不从图里删**：「我不再看见它」和「它不在了」是两个断言，只有产出方分得清。消费方降级渲染，不当作消失。
- **`dispute` 与 `state == "disputed"` 严格互为充要**，键 ⊆ `witnesses`，值取自同一分类表且必须真的不同。缺了它，图只记录「有过分歧」而不记录分歧内容，而人裁决恰恰只需要后者。
- **`witnesses` 必须含标签自身的 `source`**；`label_id` 图内唯一；空 `labels` 合法（空地图是真实状态）。
- **`colocalization_stale` 不是第四种消息**：它就是 `colocalization` 消息带非 `ok` 状态，共定位健康度只有一处可读。`state == "lost"` 时 **`T_map_headset` 必须整键省略**——拿单位阵顶替会把所有头显标签静默堆到地图原点（同「缺失 = 未知，禁带内哨兵」铁律）。`state == "ok"` 时 `T_map_headset` + `quality` 必填。
- **低频是硬要求，不是建议**：`scene_graph` 1–5 Hz 变更驱动、`colocalization` ≤1 Hz + 事件、`semantic_label` 事件驱动 ≤5 Hz，天花板由 `PS_MAX_HZ` + `validate_ps_stream` 实测校验。有多条观测要发就**批进一条 `semantic_label`**（body 收数组），不要连发。**变更驱动 = 没变更就该静默**，1 Hz 是标称下限不是心跳，消费方不要照它实现 keep-alive。

### 消费方解阻塞（PS0 已定稿，以下可开工）

- **Daedalus（PS1 机器人端识别 / PS2a 融合 / PS3 桥接，C12 消费方 + ADR-004 Owner）**：`pip` 升 `mnesis-canonical` 后 `from mnesis_canonical import validate_observation_label, validate_scene_graph, validate_ps_message`；识别输出按 `ObservationLabel` 发，融合产物按 `scene_graph` 发（`revision` 每次变更递增），`class_id` 只用本仓分类表。8442 上按 `type` 分派三个新消息，与既有 `C3_*` 消息同信封共存。
- **Eidolon（PS2b 头显消费，C12 消费方）**：vendor `mnesis_canonical/semantic.schema.json` 走 JS 侧 Draft 2020-12 校验；下行按 `scene_graph.revision` 判断是否重绘（不变则不重绘）；共定位健康度只读 `colocalization.state`；头显侧标注上行走 `semantic_label`（`source: "headset"`，人裁决 `source: "human"`），发前先用 `T_map_headset` 变换到 `map`。**头显侧识别（PS4）落地时不需要改契约**——枚举已就位。
- **两端共用**：`examples/semantic/` 四个 golden 样本（含 `disputed` / `stale` / `source:"headset"` 三个边界样本）直接当 fixture 用。
- **未动 `contracts/`**：PS 消息不改 C1 帧、不改 C3 既有消息，故 `contracts/*.md` 与 `contracts.lock` 本次零改动（本仓契约只读纪律）。C3 侧若要把这三个消息一并镜像进 `XR_ROBOT_CONTRACT.md`，属 Daedalus（C3 Owner）的独立卡。

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

### 消费端升版路径（C3 v1.7 · WebRTC 信令三消息，issue #60）

- **所有消费方**：`contracts.lock` 已重算，执行 `python -m mnesis_canonical.contracts_check --generate` 更新本地锁。`webrtc_signaling.schema.json` 为新增文件，首次加入 `contracts.lock` 跟踪范围。
- **Daedalus**（C3 Owner，xr_bridge 服务端）：将 `docs/integration/XR_ROBOT_CONTRACT.md` 镜像同步到 v1.7；在 WS 信令处理器中新增 `video_offer` 接收 → `video_answer` 应答 → `video_ice` 双向中继（**信令流走 8442 WS 信封，媒体流走 WebRTC DTLS/SRTP 直连，不经过 8442**）。多订阅者场景：`stream_id` 关联编码器，`subscriber_id` 区分各 peer 的 PeerConnection。harness 新增 WebRTC 信令回合测试。**≤v1.6 客户端零改动**：未实现 `video_offer`/`video_answer`/`video_ice` 的旧客户端，视频退回到 MJPEG 线，行为不变。
- **Eidolon**（C3 消费方，Quest 前端 + Web 前端）：升到 v1.7 后，Web 端常开（建图/3DGS 采集）和 Quest 端按需接入（精细操作）均可通过 `video_offer` 发起 WebRTC 协商。`subscriber_id` 区分两端——`"web_dashboard_1"` 与 `"quest_2"` 可同时订阅同一路 `stream_id`。`qos_hint` 按场景设置：Quest 端 → `"low_latency"`，Web 端 → `"stable"`。未升版时忽略 `video_*` 消息，视频退回到 MJPEG，遥操作核心不受影响。
- **Ambrosia**（Web 控制台消费方，YC 后接入）：虽然 `video_*` 消息是 C3 线侧信令（不经过 C2 上传），但 Ambrosia 控制台的 Web 版视频预览需要消费 `video_offer`/`video_answer`/`video_ice` 建立 WebRTC 流。升版后按 `C3_Info.video_capabilities` 发现 `webrtc` 线，通过 `video_offer` 发起协商。`C3_CameraControl` 协商的 `codec`/`width`/`height`/`fps` 参数在 WebRTC 线中通过 SDP 传递，两套协商机制互补（`C3_CameraControl` 定参数 → `video_offer` 传 SDP）。

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

### C9 · `camera_intrinsics` 一等字段（**已转正 v1，见上方主表**）
> 已转正为 C9 v1：`SPEC.md` §Camera intrinsics + `embodiments/embodiment.schema.json` `capture.cameras[].intrinsics`。含畸变模型枚举（`pinhole` / `pinhole_radtan` / `kannala_brandt` / `double_sphere`）。
>
> 以下为原草案登记内容，保留供追溯：
>
> 相机内参(fx,fy,cx,cy,畸变,分辨率)应是 **canonical 一等字段**,不塞各仓私有 sidecar。两采集面同表示后,**4DGS/重构才能同吃手机+Quest 帧**。Owner=canonical 定义;消费方=Iris·Eidolon 产出、Ambrosia/重构消费。

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
