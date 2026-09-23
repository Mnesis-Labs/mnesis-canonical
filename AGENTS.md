# AGENTS.md

本仓给 AI agent 的约定。跨仓规则以 Parthenon 为准。

## Cline CLI 使用机制（2026-09-23，全仓统一）

真值在 Parthenon [`docs/CLINE-CLI.md`](https://github.com/Mnesis-Labs/Parthenon/blob/main/docs/CLINE-CLI.md)（合并前见 [Parthenon#859](https://github.com/Mnesis-Labs/Parthenon/pull/859)）。规则只在那里改，这里只是指针。

- **派单 root 只有「Mnesis 多仓库 Tech Lead」会话。** Cline 是辅助执行者：不当编排者，不写 `D:/Github/_ops/mr-fusion-0921/dispatch-state.json`，不停别人的 worker。同一 worktree 同一时刻只有一个 worker 写。
- **派 Cline 任务只用这一条命令**：`python D:/Github/Parthenon/cockpit/scripts/cline_run.py --cwd <worktree 绝对路径> --prompt-file <任务说明.md> --task <任务名>`（Parthenon#859 合并并更新本地检出前，脚本在 `D:/Github/_wt/parthenon-cline-fallback/cockpit/scripts/cline_run.py`）。
- **免费档四个模型自动切换**：MiMo-V2.6-Flash → DeepSeek V4.1 Flash → Kimi K3 → Muse Spark 1.3 Contributor。触发当日额度就自动换下一个，接着做同一个任务。四个都用完时，脚本弹通知并以退出码 **42** 结束，派单方要转告 Muso 换 Cline 账号，不要重试。换账号后额度记录自动清空。
- 不要手写 `cline -p`（无头会一直等批准），不要直调 `cline.exe`、带 `HTTP(S)_PROXY`，也不要用 `--id` 续接会话。这些坑都已写进脚本里处理。
