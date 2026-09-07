"""连续开发队列 —— 逐卡串行跑 dev_local，可断点续跑。

用法:
    python scripts/run_queue.py 806 805 779

为什么要有这个文件（2026-09-01 教训，Daedalus 侧实证）：此前用
`nohup python - <<EOF ... &` 起队列，进程在调用返回时即被杀，队列**一张卡都
没跑**却显示「已发车」。落成文件 + 由后台任务托管，进度写进 PROGRESS 日志，
不再有隐形失败。

每张卡的开发实际发生在 `.claude/worktrees/dl-issue-<N>/`（独立 git worktree），
worker 是无头 claude CLI；本脚本只负责排队与记账，**不 push、不开 PR**。
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PROGRESS = REPO_ROOT / ".claude" / "queue_progress.log"
PY = sys.executable

# 退出码语义。与 dev_local.py 一一对应 —— 改一处必须改另一处。
# 之所以逐码写清楚：2026-09-02 实测，日志把「跳过」打成「rc=0（0=验收过）」，
# 看日志的人会以为这张卡我们做过了。退出码是给人读的，含混就等于说谎。
_RC_MEANING = {
    0: "验收通过 —— 读 diff → 推 → 等 CI → 合",
    2: "网关钥匙缺失 —— 修配置，不是工人不行",
    3: "读卡失败 —— 网络/权限",
    4: "工人零产出 —— 看 result 的 tail，多半是卡本身描述不足",
    5: "验收未过（pytest 红）—— 看 acceptance_fail",
    6: "尝试用尽 —— **worktree 里可能有半成品，看 result 的 has_partial_work**",
    7: "跳过（卡已关）—— 不是失败也不是完成，多半别人先做掉了",
    8: "**工人超时被杀** —— worktree 里是半成品；验收结果仅供参考，必须人工逐项复核后才可推",
    9: "**引擎崩溃**（CLI 零轮次零开销）—— 不是做不出来，别改卡描述；查 CLI/网关后原样重派",
    10: "⛔ **网关后端故障**（No connected db）—— 工人一轮都没跑过。先修网关，别改卡、别重试",
}


def note(msg: str) -> None:
    line = f"[{time.strftime('%m-%d %H:%M')}] {msg}"
    print(line, flush=True)
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    with PROGRESS.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def running_dev_local() -> int:
    """当前有几个 dev_local 在跑（Windows 会为同一进程显示父子两条，故取半）。

    必须排除 powershell.exe 自己：这条探测命令的**命令行里就含 'dev_local.py'
    这个字符串**，于是它会把自己数进去。2026-09-02 首跑实测：真实并发 3，读数
    却是 4，多出来的那个就是探测进程本身。这类自匹配在低并发时被 tolerate
    盖住不发作，等到「明明没人在跑却一直等」时才暴露 —— 与本仓 silent-failure
    清单里「守卫读到的是自己」同型。
    """
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-CimInstance Win32_Process | Where-Object { "
         "$_.CommandLine -match 'dev_local\\.py' -and $_.Name -ne 'powershell.exe' "
         "}).Count"],
        capture_output=True, text=True)
    n = (r.stdout or "0").strip() or "0"
    return (int(n) // 2) if n.isdigit() else 0


def wait_for_idle(max_wait_s: int = 90 * 60, tolerate: int = 2) -> None:
    """等到并发的 dev_local 落到 tolerate 以下再开工。

    为什么要等：网关在多路长流并发时会掐线（Parthenon#785 实证），两个队列
    同时跑会互相拖垮。为什么容忍少量：别的会话/别的仓可能也在跑，不该被无限期挡住。
    """
    deadline = time.time() + max_wait_s
    announced = False
    while time.time() < deadline:
        n = running_dev_local()
        if n <= tolerate:
            if announced:
                note(f"并发已降到 {n}，开工")
            return
        if not announced:
            note(f"并发 {n} 高于 {tolerate}，等待…")
            announced = True
        time.sleep(60)
    note("等待超时，仍然开工（宁可撞车也不无限期饿死）")


def main() -> int:
    nums = [int(a) for a in sys.argv[1:]]
    if not nums:
        print(__doc__)
        return 1
    note(f"队列发车：{nums}")
    for i, n in enumerate(nums, 1):
        wait_for_idle()
        note(f"({i}/{len(nums)}) 开跑 #{n}")
        rc = subprocess.run([PY, "scripts/dev_local.py", str(n)], cwd=REPO_ROOT).returncode
        note(f"({i}/{len(nums)}) #{n} 结束 rc={rc} "
             f"（{_RC_MEANING.get(rc, '未知码')}）")
    note("队列跑完")
    return 0


if __name__ == "__main__":
    sys.exit(main())
