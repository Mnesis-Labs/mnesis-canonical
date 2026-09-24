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
