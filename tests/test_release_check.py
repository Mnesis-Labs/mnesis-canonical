"""Tests for ``scripts/release_check.py``.

Failure injection goes through the ``_run`` seam / a monkeypatched ``shutil.which``
so no real repo file is broken and no nested release-check subprocess is spawned.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

SUMMARY_RE = re.compile(r"^RELEASE_CHECK summary passed=\d+ failed=\d+ skipped=\d+$")
_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "release_check.py"


def _load():
    spec = importlib.util.spec_from_file_location("release_check", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["release_check"] = module
    spec.loader.exec_module(module)
    return module


rc = _load()


@pytest.fixture
def all_tools(monkeypatch):
    """Pretend every external executable (ruff, pyright) is installed."""
    monkeypatch.setattr(rc.shutil, "which", lambda name: f"/usr/bin/{name}")


def _stub_run(monkeypatch, failing_labels=()):
    def fake(step):
        if step.label in failing_labels:
            return 1, f"boom: {step.label}"
        return 0, "ok"

    monkeypatch.setattr(rc, "_run", fake)


def test_sections_cover_checklist_2_to_6():
    keys = [s.key for s in rc.build_sections()]
    assert keys == ["contracts", "embodiments", "lint", "tests", "smoke"]


def test_all_green_exits_zero_with_summary_last_line(all_tools, monkeypatch, capsys):
    _stub_run(monkeypatch)
    assert rc.main([]) == 0
    out = capsys.readouterr().out
    lines = out.strip().splitlines()
    assert SUMMARY_RE.match(lines[-1]), lines[-1]
    assert "failed=0" in lines[-1]
    # §1/§7/§8 stay manual — reminded, never executed.
    assert "§1 version bump" in out and "§7 git tag" in out and "§8 GitHub Release" in out


@pytest.mark.parametrize(
    ("label", "section"),
    [
        ("python -m mnesis_canonical.contracts_check", "contracts"),
        ("python -m mnesis_canonical.embodiment_check", "embodiments"),
        ("ruff check .", "lint"),
        ("pytest -q", "tests"),
        ("python -m mnesis_canonical --help", "smoke"),
    ],
)
def test_broken_section_exits_one_and_names_the_section(
    all_tools, monkeypatch, capsys, label, section
):
    _stub_run(monkeypatch, failing_labels={label})
    assert rc.main([]) == 1
    out = capsys.readouterr().out
    assert f"FAILED sections: {section}" in out
    assert "failed=1" in out.strip().splitlines()[-1]
    assert SUMMARY_RE.match(out.strip().splitlines()[-1])


def test_only_runs_a_single_section(all_tools, monkeypatch, capsys):
    _stub_run(monkeypatch, failing_labels={"pytest -q"})
    assert rc.main(["--only", "contracts"]) == 0
    out = capsys.readouterr().out
    assert "§2 Contracts integrity" in out
    assert "§5 Tests" not in out


def test_advisory_step_failure_is_skip_but_gates_under_strict(all_tools, monkeypatch, capsys):
    advisory = "python -m mnesis_canonical.importers list"
    _stub_run(monkeypatch, failing_labels={advisory})

    assert rc.main(["--only", "smoke"]) == 0
    assert f"[SKIP] {advisory}" in capsys.readouterr().out

    assert rc.main(["--only", "smoke", "--strict"]) == 1
    assert "FAILED sections: smoke" in capsys.readouterr().out


def test_missing_ruff_fails_but_missing_pyright_only_skips(monkeypatch, capsys):
    monkeypatch.setattr(rc.shutil, "which", lambda name: None)
    _stub_run(monkeypatch)
    assert rc.main(["--only", "lint"]) == 1
    out = capsys.readouterr().out
    assert "[FAIL] ruff check ." in out
    assert "[SKIP] pyright ." in out
    assert "pyright not on PATH" in out


def test_pyright_errors_are_fail_not_skip(monkeypatch, capsys):
    """pyright is no longer advisory — when installed, errors are a hard gate."""
    monkeypatch.setattr(rc.shutil, "which", lambda name: f"/usr/bin/{name}")
    _stub_run(monkeypatch, failing_labels={"pyright ."})
    assert rc.main(["--only", "lint"]) == 1
    out = capsys.readouterr().out
    assert "[FAIL] pyright ." in out