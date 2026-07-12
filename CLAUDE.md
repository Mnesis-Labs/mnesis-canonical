# mnesis-canonical · Agent 开发纪律（Worker Constitution）
角色：本仓 worker，只处理指派的单个 issue。
边界锁：只改本仓文件；对兄弟仓的意见用 `gh issue create --repo Mnesis-Labs/Parthenon` 提案，禁止直接改其他仓。
契约只读：contracts / *.lock 需改动则在 PR 说明并停下，等 PM 走 type:contract-change 流程。
栈：Python 纯标准库开放标准（schema/validate/io/lerobot/isaac/manifest）
测试纪律（合并前必须通过）：ruff check . ; pytest -q
提交：分支 agent/issue-<N>；PR 含 Closes #<N> + 验收自查。
可信状态：merged/CI 等断言以 gh api 真实返回为准。
完成：改代码→本地测试通过→开 PR→停止（评审与合并不归你管）。
