"""Self-hosted CI legs must not depend on downloading a marketplace action (#126).

`main` went red for 4+ hours with three of four jobs dying in "Set up job" — the
runners could not fetch `actions/checkout@v4` from codeload.github.com (429 Too
Many Requests on the Windows box, an SSL failure on the mac one).  No repo code
ran at all, yet every PR opened afterwards inherited the failure and looked like
it had a problem of its own.

The runner re-downloads an action for *every* job rather than reusing a cache, so
four jobs × push-and-pull_request double-triggering is eight codeload fetches per
push, all from one Chinese proxy egress — the rate limit is structural, not bad
luck.  The self-hosted legs now check out with the runner's own git.

This guard is text-based on purpose: the repo is pure standard library, so there
is no YAML parser to lean on.  `uses:` on a hosted runner is fine (ci-fast.yml),
which is why the check is scoped to the workflows that run on `[self-hosted]`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"

# ci-fast.yml runs on ubuntu-latest, where action downloads go over GitHub's own
# network and have never failed; it keeps actions/checkout deliberately.
_SELF_HOSTED_WORKFLOWS = ("ci.yml", "release.yml")

_USES = re.compile(r"^\s*(?:-\s+)?uses:\s*(\S+)", re.MULTILINE)


@pytest.mark.parametrize("name", _SELF_HOSTED_WORKFLOWS)
def test_self_hosted_workflow_downloads_no_actions(name):
    text = (_WORKFLOWS / name).read_text(encoding="utf-8")
    assert _USES.findall(text) == [], (
        f"{name} runs on self-hosted runners; every `uses:` is a codeload fetch "
        f"that can 429 and kill the job before any repo code runs (#126)"
    )


@pytest.mark.parametrize("name", _SELF_HOSTED_WORKFLOWS)
def test_self_hosted_workflow_checks_out_the_triggering_commit(name):
    """Whatever replaces actions/checkout still has to land on $GITHUB_SHA."""
    text = (_WORKFLOWS / name).read_text(encoding="utf-8")
    assert "runs-on: [self-hosted]" in text
    assert 'git fetch -q --no-tags --depth=1 origin "$GITHUB_SHA"' in text
    assert "git checkout -q --detach FETCH_HEAD" in text


def test_ci_fast_still_runs_on_a_hosted_runner():
    """If ci-fast.yml ever moves to self-hosted it must join the guard above.

    Matched on `runs-on:` lines, not the whole file — the header comment mentions
    self-hosted runners while explaining why this leg is not one.
    """
    text = (_WORKFLOWS / "ci-fast.yml").read_text(encoding="utf-8")
    targets = re.findall(r"^\s*runs-on:\s*(.+)$", text, re.MULTILINE)
    assert targets == ["ubuntu-latest"]


# ── release.yml：一条从未执行过的发布链路（#109）──────────────────────────────
# `gh run list --workflow=release.yml` 至今为空：它由推 `v*.*.*` tag 触发，而本仓
# 唯一的 tag v0.5.0 指向 07-28 的提交，**早于该 workflow 落地（#98，08-09）**——
# 已存在的 tag 再推是 no-op。所以 PyPI 上没有这个包，而 GitHub Release v0.5.0 是
# 手工建的，不是这条链路的产物。
#
# ci.yml 每次推送都在跑，它的写法有实测背书；release.yml 一次没跑过，里面每一行
# 都是未验证假设。下面这组守卫把「首次真发布必死」的几处钉住，让它们至少不必等到
# 那一次不可逆的上传才暴露。守卫仍然是文本匹配：本仓零运行时依赖，没有 YAML 解析器。
_RELEASE = _WORKFLOWS / "release.yml"

# 步骤起始行：6 空格 + "- "。run: 块里的正文缩进都更深，不会误命中。
_STEP_START = re.compile(r"^      - ", re.MULTILINE)


def _release_steps() -> list[str]:
    """Split release.yml's step list into one text block per step."""
    text = _RELEASE.read_text(encoding="utf-8")
    starts = [m.start() for m in _STEP_START.finditer(text)]
    assert starts, "no steps found — has release.yml's indentation changed?"
    ends = [*starts[1:], len(text)]
    return [text[a:b] for a, b in zip(starts, ends, strict=True)]


def test_every_release_step_declares_a_shell():
    """The #126 trap, applied to the leg that has no runtime evidence at all.

    On this Windows self-hosted runner a step with no `shell:` runs under pwsh.
    `GitHub Release` was written in bash (`TAG="${GITHUB_REF_NAME}"`, `awk`,
    `[ -z ... ]`) and declared no shell, so the first real release would have died
    there — after the PyPI upload half of the job had already happened.

    Scoped to release.yml on purpose: ci.yml's bare `- run:` steps are single
    native commands that have run green on both machines thousands of times.
    """
    missing = [
        step.splitlines()[0].strip()
        for step in _release_steps()
        if re.search(r"^\s+run:", step, re.MULTILINE)
        and not re.search(r"^\s+shell:", step, re.MULTILINE)
    ]
    assert missing == [], (
        f"release.yml steps with `run:` but no `shell:`: {missing} — they run under "
        f"pwsh on the Windows self-hosted runner (#126)"
    )


def test_release_overrides_the_pip_index():
    """§5 runs `pip wheel` through the runner's global pip config (#103).

    `release_check.py` → `pytest -q` → `tests/test_wheel_install.py` shells out to
    `python -m pip wheel` with no `--index-url`, so it inherits the machine config
    pointing at a mirror that IP-bans this box. ci.yml overrides it at workflow
    level; release.yml is a second, independent code path into the same fault and
    needs its own copy — missing exactly the way #103 was missed the first time.
    """
    text = _RELEASE.read_text(encoding="utf-8")
    assert "PIP_INDEX_URL:" in text and "PIP_EXTRA_INDEX_URL:" in text


def test_pypi_upload_precedes_the_github_release():
    """Announce only what is already installable.

    A GitHub Release created *before* the upload leaves exactly the artifact the
    #109 sentinel exists to catch: a repo that says vX shipped while
    `pip install mnesis-canonical` 404s. It also burns the tag — PyPI never allows
    re-uploading a version, and a retry needs a human to delete the Release first.
    """
    text = _RELEASE.read_text(encoding="utf-8")
    upload = text.index("- name: Publish to PyPI")
    release = text.index("- name: GitHub Release")
    assert upload < release, (
        "release.yml announces the GitHub Release before the package is on PyPI"
    )


def test_release_preflights_the_pypi_token():
    """The credential check must come before anything irreversible.

    PYPI_TOKEN's presence has never been observed (`gh secret list` needs admin),
    so "the secret is set" is an assumption, not a fact. Checking it in step one
    turns a missing secret into a 5-second red instead of a half-published tag.
    """
    steps = _release_steps()
    preflight = next(
        (i for i, s in enumerate(steps) if "PYPI_TOKEN" in s and "-z" in s), None
    )
    assert preflight is not None, "release.yml never asserts PYPI_TOKEN is non-empty"
    publish = next(i for i, s in enumerate(steps) if "twine upload" in s)
    assert preflight < publish


def test_release_upload_is_retryable():
    """A half-finished upload must not wedge the tag forever.

    `twine upload` without `--skip-existing` fails on the sdist it already sent
    when only the wheel half died, and that version can never be re-uploaded.
    `twine check` asks PyPI's metadata question before, not after, the announcement.
    """
    text = _RELEASE.read_text(encoding="utf-8")
    assert "twine upload --skip-existing" in text
    assert "twine check" in text


def test_release_gates_tag_against_package_version():
    """`git tag v0.9.9` on a 0.6.0 tree must not reach PyPI.

    scripts/version_check.py keeps the three in-repo version strings together
    (#76) but knows nothing about the tag, which is the fourth copy — and the only
    one that names the GitHub Release while PyPI gets the other three.
    """
    text = _RELEASE.read_text(encoding="utf-8")
    assert "GITHUB_REF_NAME#v" in text
    assert "mnesis_canonical.__version__" in text
