---
archived: 2026-08-08
superseded_by: DEV_GUIDE.md
---

# mnesis-canonical · Agent 开发纪律（Worker Constitution）
角色：本仓 worker，只处理指派的单个 issue。
边界锁：只改本仓文件；对兄弟仓的意见用 `gh issue create --repo Mnesis-Labs/Parthenon` 提案，禁止直接改其他仓。
契约只读：contracts / *.lock 需改动则在 PR 说明并停下，等 PM 走 type:contract-change 流程。
栈：Python 纯标准库开放标准（schema/validate/io/lerobot/isaac/manifest）
测试纪律（合并前必须通过）：ruff check . ; pytest -q
提交：分支 agent/issue-<N>；PR 含 Closes #<N> + 验收自查。
可信状态：merged/CI 等断言以 gh api 真实返回为准。
完成：改代码→本地测试通过→开 PR→停止（评审与合并不归你管）。

## 📌 真机文档铁律（2026-07-27）

**真机操作步骤只写在 Parthenon 的 [`HARDWARE-OPERATIONS.md`](https://github.com/Mnesis-Labs/Parthenon/blob/main/HARDWARE-OPERATIONS.md) —— 唯一入口，本仓不另起操作手册。**

- 本仓可保留**深度技术细节**（排障原理、协议规格、硬件参数），但**上机操作步骤**必须写进 Parthenon 那一份，并在其 §7 来源台账登记本仓文档。
- 新增真机验证项 → 开 issue 打 `needs:hw-verify`，自动汇聚进 Parthenon `VERIFICATION.md`。
- 测试结果回填 → Parthenon `DEVICE_TESTING.md`。

理由：真机操作曾散落 5 个仓 12 份文档（含已过时路径如 `TeleOP-Alohamini`），上机时翻找成本高且容易照着过时步骤操作。
