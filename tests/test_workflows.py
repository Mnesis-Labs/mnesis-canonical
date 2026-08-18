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
