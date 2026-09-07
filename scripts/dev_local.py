"""本地直驱开发执行器（mnesis-canonical） —— 一张卡跑一个隔离 worktree 里的无头 claude CLI。

用法:
    python scripts/dev_local.py 806
    python scripts/dev_local.py 806 --model kimi-k3 --max-attempts 2

设计取自 Mnesis-Daedalus/scripts/dev_local.py（2026-08-28 起在 Daedalus 实跑，
全舰队合并量最高的一条线），本文件是 Parthenon 侧的移植。**不是新发明**，
每一处古怪写法都对应那边踩过的坑，改动前先读注释。

与旧 lane/worker 体系的根本区别 —— 这三条就是 2026-09-01 换代的全部理由:
  1. **不自动领卡**。issue 号由人/主会话显式传入。没有标签轮询、没有认领仲裁、
     没有孤儿回收，因此不存在双派、不存在 ready↔wip↔blocked 死循环。
  2. **不 push、不开 PR**。跑完只把产出留在 worktree + 写一份 result JSON。
     推不推、合不合，是主会话读完 diff 之后的**单独动作**。
  3. **跑不动就大声说**。引擎不可用 / 网关掐线 / 超时，各有可区分的退出码与
     result 字段；绝不静默换引擎，也绝不把「跑了但没产出」伪装成成功。
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

REPO = "Mnesis-Labs/mnesis-canonical"
MAX_TRANSPORT_RETRIES = 8  # 网关抖动的重试上限（不计入 max_attempts）

# 网关/传输层故障的指纹 —— 这些**不是工人的错**，不该消耗开发尝试次数。
# 2026-09-01 实证（Daedalus 侧）：一轮 10 卡队列里 5 张死于此，每张烧光
# max_attempts 后被判 blocked、产出丢弃。根因在 Parthenon#785（网关掐长流）。
_TRANSPORT_ERRORS = (
    "Connection closed mid-response",
    "Unable to connect to API",
    "ECONNRESET",
    "ETIMEDOUT",
    "socket hang up",
    "502 Bad Gateway",
    "503 Service Unavailable",
    # 2026-09-05：model=auto 专属。CLI 有时发超限的思考预算，被上游 400 拒：
    #   field Thinking.BudgetTokens invalid, should be at most 1024
    # 而网关**没给 auto 配降级组**（报错原文 `Available Model Group Fallbacks=None`），
    # 主路一错就没退路 —— kimi-k3 有一整条 glm-5.2→deepseek-pro→… 的链，auto 没有。
    # 实测失败率：裸 auto 4 次 2 败；加 MAX_THINKING_TOKENS=1024 后 6 次 1 败。
    # 这是**基础设施故障不是工人的错**，归进传输层桶 = 重试且不消耗尝试次数。
    "Thinking.BudgetTokens invalid",
    "No fallback model group found",
)

GATEWAY_URL_FILE = pathlib.Path("D:/Github/_ops/secrets/console.url")
GATEWAY_KEY_FILE = pathlib.Path("D:/Github/_ops/secrets/console.key")
WORKER_HOME = "D:/Github/_ops/claude-worker-home"
# 2026-09-05 Muso 指示：开发/调研一律走 CLI，模型用 `auto`（网关侧自动路由）。
# 上线前实测过，不是照抄配置：
#   POST <gateway>/v1/messages {"model":"auto",...} → HTTP 200，
#   响应体 {"model":"auto","content":[{"type":"text","text":"OK"}]}，正常出词。
# （今天刚栽过一次「把推断当实测」—— #832 里我拿 /v1/models 的列表推出「某模型不可用」，
#  实打才发现网关认那个别名。所以换模型名这类改动，先打一次再改。）
DEFAULT_MODEL = "auto"
PY = sys.executable


def is_transport_error(out: str) -> bool:
    """工人输出是否表明它死于网关/传输故障（而非任务本身做不动）。"""
    return any(sig in out for sig in _TRANSPORT_ERRORS)


def is_engine_crash(out: str) -> bool:
    """CLI 自己崩了 —— 工人**一轮都没跑过**，不是「做不出来」。

    2026-09-03 实测（#821）：两次尝试都拿到

        {"type":"result","subtype":"error_during_execution","num_turns":0,
         "total_cost_usd":0,"is_error":true,
         "errors":["undefined is not an object (evaluating 'e.includes')"]}

    `num_turns:0` + `total_cost_usd:0` = 一个 token 都没花，任务根本没开始。
    而执行器当时把它判成 rc=4「工人零产出 —— 多半是卡本身描述不足」——
    **诊断完全错了**，会让人去改卡的描述，而卡一个字都没问题。

    这就是 #234 定下的那条纪律：**「引擎不可用」必须与「做不出来」可区分**。
    同 silent-failure 清单里反复出现的形态：失败长得和另一种失败一样。
    """
    if '"subtype":"error_during_execution"' in out:
        return True
    # 兜底：明确的零轮次 + 零开销，无论 subtype 叫什么
    return '"num_turns":0' in out and '"total_cost_usd":0' in out


# 2026-09-06：`auto` 路由在**真实负载**下会间歇性变得不可用，CLI 直接回这一句：
#     There's an issue with the selected model (auto).
#     It may not exist or you may not have access to it.
# 实测边界（这条边界很重要，别照抄结论）：
#   · 一句话 prompt：6 次 1 败
#   · 中等 prompt（一段说明文）：三种配置各 1 次，全通
#   · **真活（#835，长正文+评论+多轮工具调用）：两轮尝试全灭**
# 也就是说「冒烟通过」完全不能代表「真活跑得动」—— 同 #832 那次「拿最小探针
# 代替真实路径」的教训。
_MODEL_UNAVAILABLE_MARKERS = (
    "issue with the selected model",
    "It may not exist or you may not have access to it",
)

# `auto` 不可用时的退路。**网关侧没给 auto 配降级组**（实测报错原文
# `Available Model Group Fallbacks=None`），所以这条链必须由执行器提供。
# kimi-k3 是全舰队长期实跑的模型，且它在网关侧自带
# glm-5.2 → deepseek-pro → deepseek → … 的降级链。
FALLBACK_MODEL = "kimi-k3"


def is_model_unavailable(out: str) -> bool:
    """CLI 说「这个模型用不了」—— 不是工人的错，也不是网络抖动。"""
    return any(sig in out for sig in _MODEL_UNAVAILABLE_MARKERS)


# 2026-09-07：网关**后端**故障。与「网络抖动」不同 —— 抖动重试能好，这个不能：
#     API Error: 400 {"error":{"message":"No connected db.","type":"no_db_connection"}}
# 实测当天两个入口（49.235.157.202:9400 与 nextscene.cn/llm）返回同一错误，
# 说明后者只是同一 LiteLLM 实例前面的反代，**没有独立的第二条网关可退**。
#
# 为什么单独一类：它出现时工人一轮都没跑过、零产出，而执行器原本把零产出判成
#   「rc=4 工人零产出 —— 多半是卡本身描述不足」
# ——**诊断完全错了**，会让人去改一张一个字都没问题的卡。这正是 #234 定的那条
# 纪律：「引擎不可用」必须与「做不出来」可区分。2026-09-07 它咬了一口：#833 与
# canonical#150 同时被误判成「卡描述不足」。
_GATEWAY_DOWN_MARKERS = (
    "No connected db",
    "no_db_connection",
)


def is_gateway_down(out: str) -> bool:
    """网关后端挂了 —— 不是工人的错，也不是能靠重试解决的抖动。"""
    return any(sig in out for sig in _GATEWAY_DOWN_MARKERS)


def _main_repo_root() -> pathlib.Path:
    """主检出根目录。脚本可能从任意 worktree 被调用，直接取 parent 会把新
    worktree 套进当前 worktree。git-common-dir 指主仓 .git。"""
    out = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=pathlib.Path(__file__).resolve().parent,
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return pathlib.Path(out).parent


REPO_ROOT = _main_repo_root()


def note(msg: str) -> None:
    print(f"[{time.strftime('%m-%d %H:%M:%S')}] {msg}", flush=True)


def sh(args: list[str], cwd=None, env=None, timeout: int = 3600,
       check: bool = False) -> subprocess.CompletedProcess:
    p = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    if check and p.returncode != 0:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(args)}\n{p.stderr[-2000:]}")
    return p


def gateway_env(model: str) -> dict:
    """构造 claude CLI 的网关环境。逐条对应 run-worker.ps1 踩过的坑。"""
    url = GATEWAY_URL_FILE.read_text(encoding="utf-8").strip()
    key = GATEWAY_KEY_FILE.read_text(encoding="utf-8").strip()
    env = dict(os.environ)
    # 补丁一：清掉可能指向别处的残留 —— 混合环境是「把网关 token 发去真
    # Anthropic 端点然后 401」的来源（run-worker.ps1:555 同款）。
    env.pop("ANTHROPIC_API_KEY", None)
    env.update({
        "ANTHROPIC_BASE_URL": url,
        "ANTHROPIC_AUTH_TOKEN": key,
        "ANTHROPIC_MODEL": model,
        "ANTHROPIC_DEFAULT_SONNET_MODEL": model,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": model,
        "ANTHROPIC_DEFAULT_OPUS_MODEL": model,
        # 补丁二：隔离 CLI 登录态。否则 OAuth 优先于 env token，静默烧订阅额度
        # 且模型不是你以为的那个。
        "CLAUDE_CONFIG_DIR": WORKER_HOME,
        # 补丁三：网关是直连 IP，必须绕过本机代理，否则 UnsupportedProxyProtocol
        # 会伪装成「网关故障」。
        "NO_PROXY": url.split("://", 1)[-1].split(":")[0] + ",localhost,127.0.0.1",
        # 补丁四（2026-09-05，model=auto 起）：钉住思考预算。上游对 auto 路由的
        # 硬上限是 1024，CLI 默认会发更大的值 → 400 直接失败。实测：不钉 4 次 2 败，
        # 钉了 6 次 1 败。残余失败由 _TRANSPORT_ERRORS 的重试兜。
        "MAX_THINKING_TOKENS": "1024",
    })
    return env


def run_claude(prompt: str, model: str, cwd: str, timeout: int = 5400) -> tuple[int, str]:
    """无头跑一次 claude CLI。返回 (returncode, 输出)。"""
    # Windows 下 subprocess 不解析 PATH 上的 .cmd shim，必须给完整路径。
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("claude CLI not found on PATH")
    # prompt 走 **stdin** 而不是 argv：.CMD shim 经 cmd.exe 转发 argv 时，多行
    # prompt 在首个换行处被截断 —— 工人只会看到第一行，然后自述「我不知道这张
    # 卡要什么」。stdin 不经 cmd.exe 的参数解析，任意长度与字符都安全。
    try:
        p = subprocess.run(
            [exe, "-p", "--model", model, "--dangerously-skip-permissions"],
            input=prompt, cwd=cwd, env=gateway_env(model), timeout=timeout,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        # 超时不许炸栈：炸栈会跳过收尾、损失现场信息。当作一次失败尝试返回，
        # 工人已落盘的产出仍在 worktree 里，可人工收割。
        return 124, f"[dev_local] worker timed out after {timeout}s; partial work kept in worktree"
    tail = (p.stdout or "")
    if p.returncode:
        tail += "\n[stderr] " + (p.stderr or "")[-1500:]
    return p.returncode, tail


def acceptance(worktree: pathlib.Path) -> tuple[bool, str]:
    """机器验收。**必须与 .github/workflows 一致**：本仓走 uv，不是裸 python -m pytest。

    2026-09-02 移植时实测：仓内 `.venv` 里根本没有 pytest（`No module named pytest`），
    因为 CI 用的是 `uv venv --seed` + `uv pip install -e ".[dev]"` + `uv run pytest -q`。
    照抄 Parthenon 那版（无 venv、裸 pytest）会让每个工人一启动就「验收未过」，
    而它的活其实是好的 —— 与 #813「验收判据被环境污染」同型，只是这次错在解释器。
    实测基线（2026-09-02，主检出）：ruff All checks passed / 666 passed。
    """
    uv = shutil.which("uv")
    if not uv:
        return False, "本机没有 uv，而本仓 CI 全程用 uv —— 装 uv 再跑，绝不回落裸 pytest 假装在测"
    r = sh([uv, "run", "ruff", "check", "."], cwd=worktree, timeout=600)
    if r.returncode != 0:
        return False, "[ruff]" + chr(10) + (r.stdout or "")[-2000:] + (r.stderr or "")[-800:]
    p = sh([uv, "run", "pytest", "-q"], cwd=worktree, timeout=1800)
    if p.returncode == 0:
        return True, ""
    return False, "[pytest]" + chr(10) + (p.stdout or "")[-3000:] + (p.stderr or "")[-1000:]


def fetch_comments(issue_num: int, max_chars: int = 12000) -> str:
    """取卡上的评论。**不取评论 = 工人看不到订正**。

    2026-09-02 实证：#818 的建议方案里指着两个已退役的组件（sentinel / auto-merge），
    规划者把这条订正写在**评论**里，而工人只拿到 title+body —— 它会照着正文里那个
    已经错的方案做，而且做得越认真错得越彻底。卡的正文是开卡那一刻的认识，
    评论是此后所有的修正，只喂正文等于刻意喂陈旧信息。
    """
    p = sh(["gh", "issue", "view", str(issue_num), "--repo", REPO,
            "--json", "comments"], cwd=REPO_ROOT)
    if p.returncode != 0:
        return ""
    try:
        items = json.loads(p.stdout).get("comments") or []
    except json.JSONDecodeError:
        return ""
    if not items:
        return ""
    parts = []
    for c in items:
        who = (c.get("author") or {}).get("login", "?")
        body = (c.get("body") or "").strip()
        if not body:
            continue
        parts.append(f"### 评论 · {who}（{c.get('createdAt', '')[:10]}）\n{body}")
    if not parts:
        return ""
    text = "\n\n".join(parts)
    if len(text) > max_chars:  # 留最新的，订正通常在后面
        text = "（前文过长已截断，以下为最新评论）\n\n" + text[-max_chars:]
    return text


def build_prompt(issue_num: int, title: str, body: str, comments: str = "") -> str:
    discussion = ""
    if comments:
        discussion = f"""
# 卡上的讨论（**比正文新，冲突时以此为准**）

正文是开卡那一刻的认识；下面这些是此后的订正、补充与反对意见。
如果讨论推翻了正文里的某个方案，**照讨论做，并在报告里说明你按哪条走、为什么**。

{comments}
"""
    return f"""你在 {REPO} 的一个隔离 git worktree 里，独立完成一张 issue。

# 卡 #{issue_num}：{title}

{body}
{discussion}
# 硬约束（违反其一即算失败，如实报告比假装做完重要得多）

1. **只改与本卡直接相关的文件。** 不顺手重构、不顺手格式化。
2. **不 git push、不开 PR、不动任何 issue 标签。** 你的产出留在 worktree 里，
   由人读完 diff 再决定去留。这是机制的一部分，不是限制。
3. **测试必须真跑。** 交付前自己跑 `uv run ruff check .` 与 `uv run pytest -q` 并把真实数字写进
   报告。禁止写「应该能过」「预计通过」这类没跑过的话。
4. **改了行为就要有测试焊住它。** 新写的守卫测试必须做一次变异验证：把实现改坏，
   确认测试真的变红，再改回来。只加不会红的测试等于没加。
5. **做不到就停下来说清楚。** 卡在哪、试过什么、缺什么。半成品 + 诚实报告，
   远好过编一个能过测试的假实现。

# 报告格式（最后输出，必须有）

## 结论
DONE / BLOCKED / PARTIAL

## 改了什么
逐文件一句话

## 测试
真实命令 + 真实数字（ruff 结果 + N passed, M failed）。变异验证做了没、结果是什么。

## 卡在哪（若非 DONE）
具体到「缺哪个文件/哪个权限/哪条信息」，不要写「需要进一步调研」。
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("issue", type=int)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--max-attempts", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=5400)
    args = ap.parse_args()

    n = args.issue
    out_dir = pathlib.Path("D:/Github/_ops/canonical-dev")
    out_dir.mkdir(parents=True, exist_ok=True)
    result_file = out_dir / f"i{n}.result.json"

    def write_result(**kw) -> None:
        result_file.write_text(
            json.dumps({"issue": n, "repo": REPO, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **kw},
                       ensure_ascii=False, indent=2), encoding="utf-8")

    # ── 前置体检（OPERATIONS-GUIDE「派活前置体检」）─────────────────────────
    if not (GATEWAY_URL_FILE.exists() and GATEWAY_KEY_FILE.exists()):
        write_result(ok=False, stage="preflight", error="网关钥匙缺失（console.url/console.key）")
        note("网关钥匙缺失，拒绝启动")
        return 2

    iv = sh(["gh", "issue", "view", str(n), "--repo", REPO,
             "--json", "number,title,body,state"], cwd=REPO_ROOT)
    if iv.returncode != 0:
        write_result(ok=False, stage="preflight", error=f"读卡失败：{iv.stderr[-500:]}")
        note(f"#{n} 读卡失败")
        return 3
    issue = json.loads(iv.stdout)
    if issue["state"] != "OPEN":
        write_result(ok=False, stage="preflight", skipped=True,
                     error=f"卡已 {issue['state']}，不派（多半是别的会话/管线先做掉了）")
        note(f"#{n} 已 {issue['state']}，跳过（不是失败，也不是完成）")
        # 7 = 跳过。**不能返回 0** —— 0 的语义是「本次跑完且验收通过」，
        # 拿它表示「压根没跑」会让队列日志把跳过显示成成功（2026-09-02 实测：
        # #812 被别的会话做掉后，日志打出「rc=0（0=验收过）」，看日志的人会以为
        # 我们做了这张卡）。跳过是好事（前置体检挡住了双派），但它得说实话。
        return 7

    wt = REPO_ROOT / ".claude" / "worktrees" / f"dl-issue-{n}"
    branch = f"claude/dl-issue-{n}"
    if not wt.exists():
        sh(["git", "worktree", "add", "-B", branch, str(wt), "origin/main"],
           cwd=REPO_ROOT, check=True)
        note(f"#{n} worktree 建好：{wt}")
    else:
        note(f"#{n} 复用已有 worktree（断点续跑）")

    comments = fetch_comments(n)
    if comments:
        note(f"#{n} 带上 {comments.count('### 评论 ·')} 条评论一起喂给工人")
    prompt = build_prompt(n, issue["title"], issue["body"] or "", comments)
    transport_retries = 0
    active_model = args.model          # 实际在用的模型（可能因不可用而回退）
    model_fallback_from = None         # 若发生回退，记下原本要用的是哪个
    # ⚠️ 用 while + 手动计数，**不能用 `for attempt in range(...)` + continue**。
    # 2026-09-02 实测（#818）：那样写时，网关抖动分支里的 `continue` 会推进 for 的
    # 计数器 —— 日志打着「不计入尝试」，实际每次抖动都吃掉一次尝试。#818 那轮
    # 两次抖动直接把 max_attempts=2 耗光，判成「尝试用尽」，而 worktree 里其实
    # 有 243 行的真产出。注释照抄了 Daedalus 原件、语义没照抄，是我移植时的错。
    # 判据：抖动只加 transport_retries，**不动 attempt**；只有真正跑完一轮
    # （无论有无产出）才 attempt += 1。
    attempt = 0
    while attempt < args.max_attempts:
        note(f"#{n} 第 {attempt + 1}/{args.max_attempts} 次尝试"
             f"（model={active_model}，已容忍抖动 {transport_retries} 次）")
        rc, out = run_claude(prompt, active_model, str(wt), timeout=args.timeout)

        # 模型不可用 → 大声换一次退路模型，**绝不静默**。
        # 「绝不静默换引擎」是本管线的硬规矩（#234）：静默换会让「引擎不可用」
        # 与「做不出来」在结果里同形。这里换是有理由的（auto 在网关侧没有降级组，
        # 退路只能由执行器给），但必须让人看见换了、换成了什么、为什么。
        if is_model_unavailable(out) and active_model != FALLBACK_MODEL:
            note(f"#{n} ⚠ 模型 {active_model} 不可用（CLI 原话：模型可能不存在或无权访问）"
                 f" → 换 {FALLBACK_MODEL} 重跑，不计入尝试（attempt 仍为 {attempt}）")
            model_fallback_from = active_model
            active_model = FALLBACK_MODEL
            continue

        if is_transport_error(out) and transport_retries < MAX_TRANSPORT_RETRIES:
            transport_retries += 1
            note(f"#{n} 网关抖动（第 {transport_retries}/{MAX_TRANSPORT_RETRIES} 次），"
                 f"不计入尝试（attempt 仍为 {attempt}），30s 后重试")
            time.sleep(30)
            continue   # attempt 未自增 —— 这才是「不计入」

        # 网关后端故障要在「零产出」之前判：它必然零产出，但原因完全不同。
        # 不重试（重试治不好后端掉库），用独立退出码 10 大声退出。
        if is_gateway_down(out):
            note(f"#{n} ⛔ **网关后端故障**（No connected db）—— 工人一轮都没跑过。"
                 f"这不是卡的问题，也不是重试能解决的：请先修网关再重派。")
            write_result(ok=False, stage="gateway_down", rc=rc, attempt=attempt,
                         model_used=active_model, model_fallback_from=model_fallback_from,
                         transport_retries=transport_retries,
                         error="网关后端不可用（No connected db）—— 与「工人做不出来」无关",
                         tail=out[-2000:])
            return 10

        # 引擎崩溃与网关抖动同属「不是工人的错」，但**不重试**：抖动是瞬时的，
        # CLI 崩溃重试也是同样的崩。大声失败、用独立退出码 9，别让人去改卡描述。
        if is_engine_crash(out):
            write_result(ok=False, stage="engine", rc=rc, engine_crash=True,
                         transport_retries=transport_retries,
                         error="Claude Code CLI 自身崩溃（零轮次、零开销），任务从未开始",
                         tail=out[-3000:])
            note(f"#{n} **引擎崩溃**（CLI 一轮没跑、一个 token 没花）—— "
                 f"不是做不出来，别改卡描述；先查 CLI/网关，再原样重派")
            return 9

        attempt += 1
        diff = sh(["git", "status", "--porcelain"], cwd=wt).stdout.strip()
        if not diff:
            note(f"#{n} 本次尝试零产出（rc={rc}，model={active_model}）")
            if attempt == args.max_attempts:
                write_result(ok=False, stage="develop", rc=rc, transport_retries=transport_retries,
                             error="工人零产出", tail=out[-3000:],
                             model_used=active_model, model_fallback_from=model_fallback_from)
                return 4
            continue

        acc_ok, fail = acceptance(wt)
        # ⚠️ 「跑完了没有」与「产出好不好」是两个正交的问题，各用一个字段答（#825）。
        # 2026-09-02 实测（#823）：工人撞 90 分钟超时被杀（rc=124），产出恰好过了验收，
        # 于是被写成 ok=true / stage=done —— 而 ok=true 与 rc=124 语义互斥：前者说
        # 「可以交付」，后者说「没跑完就被杀了」。**验收回答不了「它想做的事做完没有」**，
        # 测试只能证明「已写下的部分没把仓弄坏」。那次靠人逐项复核才没出事，
        # 但判据本身是错的。超时一律不算通过，用独立退出码 8 与 4/5 分开。
        timed_out = (rc == 124)
        ok = acc_ok and not timed_out
        write_result(ok=ok,
                     stage="timeout" if timed_out else ("acceptance" if not acc_ok else "done"),
                     rc=rc, attempt=attempt, transport_retries=transport_retries,
                     model_used=active_model, model_fallback_from=model_fallback_from,
                     worktree=str(wt), branch=branch, timed_out=timed_out,
                     acceptance_passed=acc_ok, has_partial_work=True,
                     changed=diff.splitlines(), tail=out[-6000:],
                     acceptance_fail=fail if not acc_ok else "")
        if timed_out:
            note(f"#{n} **工人超时被杀**（rc=124，跑了 {args.timeout}s 上限）—— "
                 f"验收{'通过' if acc_ok else '未过'}但那只说明「已写下的部分没弄坏仓」，"
                 f"不说明活干完了。worktree 里是半成品：{wt}，必须人工逐项复核后才可推")
            return 8
        note(f"#{n} {'验收通过' if ok else '验收未过'} —— 产出在 {wt}，未 push（等人审）")
        return 0 if ok else 5

    # 尝试用尽也要如实记录 worktree 里已有的产出。
    # 2026-09-02 实测（#818）：这条出口原本只写「尝试用尽」，result JSON 里
    # changed=[] / branch=null，而 worktree 里躺着 243 行真产出 —— 看 result 的人
    # 会以为工人什么都没做出来，把可用的半成品当垃圾丢掉。
    # 「跑不完」与「没产出」是两件事，别在记账上把它们合并。
    leftover = sh(["git", "status", "--porcelain"], cwd=wt).stdout.strip()
    write_result(ok=False, stage="develop", error="尝试用尽", branch=branch,
                 worktree=str(wt), transport_retries=transport_retries,
                 changed=leftover.splitlines() if leftover else [],
                 has_partial_work=bool(leftover))
    if leftover:
        note(f"#{n} 尝试用尽，但 worktree 里有 {len(leftover.splitlines())} 个改动文件 —— "
             f"是半成品不是零产出，先去 {wt} 看一眼再决定丢不丢")
    return 6


if __name__ == "__main__":
    sys.exit(main())
