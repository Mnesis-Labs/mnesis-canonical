# 开发执行政策（2026-10-03，覆盖旧 CLI/模型角色规定）

用户已要求全面下线 Claude 账号与 Claude Code CLI。此前所有“只能使用 Claude Code CLI”“Cline 已退役”或禁止使用 Codex 执行的规定已被本次决定覆盖。

- Codex 主会话负责产品规划、任务规格、编排、独立验收和 GitHub/CI 闭环；执行助手使用 Codex CLI 的 Nextscene 专用 profile 或 Cline CLI。服务入口 https://nextscene.cn/llm，凭据由外部环境注入，禁止写入仓库、任务文本或日志；模型必须实时探活并明确指定，禁止静默降级到旧账号。
- 主政策入口：[Parthenon WORKER-POLICY](D:/Github/Parthenon/docs/WORKER-POLICY.md)。接手与退役账目：[Claude retirement](D:/Github/Parthenon/ops/claude-retirement/README.md)。远端协作读取同名仓内文档的当前版本。
- 一张任务卡、一位写入者、一个隔离 worktree；启动前检查进程、锁、脏差异、已有成果。不得抢占或覆盖他人写入领地；中断须先落盘并保留结果。
- 本仓产品、安全、协议、资产、测试与验收要求继续生效。历史工具和机器路径描述需按当前环境核验；下文的 Claude/Cline 角色旧规定仅保留作为历史来源，不能重新启用已退役执行入口。
- 完成须提供 diff、真实测试结果、未验证边界和当前提交 SHA；CLI 退出、commit、CI 绿或旧安装包均不能替代独立验收。复核当前 SHA 后明确 APPROVE/REJECT。
- 真机操作沿用 Parthenon HARDWARE-OPERATIONS.md 唯一入口与本仓现有更严格限制；无人到场不得运动，不得绕过 estop/deadman/限位。模拟、静态检查和 CI 不得标为真机验证。

## 本仓已有规则（保留）

# AGENTS.md

本仓给 AI agent 的约定。跨仓规则以 Parthenon 为准。

## Cline CLI 使用机制（2026-09-23，全仓统一）

真值在 Parthenon [`docs/CLINE-CLI.md`](https://github.com/Mnesis-Labs/Parthenon/blob/main/docs/CLINE-CLI.md)（合并前见 [Parthenon#859](https://github.com/Mnesis-Labs/Parthenon/pull/859)）。规则只在那里改，这里只是指针。

- **派单 root 只有「Mnesis 多仓库 Tech Lead」会话。** Cline 是辅助执行者：不当编排者，不写 `D:/Github/_ops/mr-fusion-0921/dispatch-state.json`，不停别人的 worker。同一 worktree 同一时刻只有一个 worker 写。
- **派 Cline 任务只用这一条命令**：`python D:/Github/Parthenon/cockpit/scripts/cline_run.py --cwd <worktree 绝对路径> --prompt-file <任务说明.md> --task <任务名>`（Parthenon#859 合并并更新本地检出前，脚本在 `D:/Github/_wt/parthenon-cline-fallback/cockpit/scripts/cline_run.py`）。
- **免费档四个模型自动切换**：MiMo-V2.6-Flash → DeepSeek V4.1 Flash → Kimi K3 → Muse Spark 1.3 Contributor。触发当日额度就自动换下一个，接着做同一个任务。四个都用完时，脚本弹通知并以退出码 **42** 结束，派单方要转告 Muso 换 Cline 账号，不要重试。换账号后额度记录自动清空。
- 不要手写 `cline -p`（无头会一直等批准），不要直调 `cline.exe`、带 `HTTP(S)_PROXY`，也不要用 `--id` 续接会话。这些坑都已写进脚本里处理。

## Worker 派单与升级规则（2026-09-24，全仓统一）

真值在 Parthenon [`docs/WORKER-POLICY.md`](https://github.com/Mnesis-Labs/Parthenon/blob/main/docs/WORKER-POLICY.md)，机器可读版是 `cockpit/data/worker-policy.json`（合并前见 [Parthenon#859](https://github.com/Mnesis-Labs/Parthenon/pull/859)）。

- **第一原则：不影响持续开发进度。** CI runner 失败，或派给 Cline CLI / Claude Code CLI 的任务中断、频繁失败（同一任务连续 2 次，或同一 CLI 24 小时内 3 次），就**收回到 Claude Desktop 对话进程，由 Opus 5.5 直接完成**。工作区里 CLI 已写好的部分保留，在它基础上接着做。
- **Cline CLI**：MiMo-V2.6-Flash、DeepSeek V4.1 Flash、Kimi K3、Muse Spark 1.3 Contributor 用于开发任务，其他免费模型用于 CI/CD。某个模型额度用完后 **24 小时**再试。付费模型（扣 Cline Credits 的）不用。
- **Claude Code CLI（LiteLLM 网关）**：kimi-k3、deepseek-pro、glm-5.2 用于开发任务，其他模型（deepseek、sensenova-lite、internlm-s1/s2、auto）用于 CI/CD。某个模型额度用完后 **5 小时**再试。
- 执行器每次非成功退出都会在 `D:/Github/_ops/escalations/` 写一条升级记录，cockpit「运维总览」页会列出来，派单 root 会话负责接手。
