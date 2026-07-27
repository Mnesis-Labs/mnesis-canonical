"""The package version must be one string, not three (#76).

`pyproject.toml` decides what a built wheel *installs as*; `__version__` decides
what the package *reports*; the CHANGELOG preamble decides what a human reads.
They drifted to 0.2.0 / 0.5.0 / 0.3.0 with nothing watching, so a consumer got a
different answer depending on which one it asked.  Pure string comparison, zero
dependencies — see `tests/test_wheel_install.py` for the installed-dist half.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import mnesis_canonical

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "version_check.py"


def _load():
    spec = importlib.util.spec_from_file_location("version_check", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["version_check"] = module
    spec.loader.exec_module(module)
    return module


vc = _load()


def test_pyproject_version_equals_dunder_version():
    assert vc.read_pyproject_version() == vc.read_dunder_version()


def test_changelog_preamble_names_the_current_version():
    assert vc.read_changelog_version() == vc.read_dunder_version()


def test_imported_package_reports_the_same_version():
    """Guard the read side too: the scraped string is the one the package serves."""
    assert mnesis_canonical.__version__ == vc.read_dunder_version()


def test_check_is_clean_and_main_exits_zero(capsys):
    assert vc.check() == []
    assert vc.main([]) == 0
    assert vc.read_dunder_version() in capsys.readouterr().out


def test_mismatch_is_reported_and_exits_one(monkeypatch, capsys):
    monkeypatch.setattr(vc, "read_pyproject_version", lambda: "0.2.0")
    problems = vc.check()
    assert len(problems) == 3
    assert vc.main([]) == 1
    out = capsys.readouterr().out
    assert "VERSION MISMATCH" in out
    assert "0.2.0" in out


def test_project_table_scoping_ignores_tool_ruff_target_version():
    """`[tool.ruff] target-version` must not be mistaken for the project version."""
    text = '[project]\nversion = "1.2.3"\n\n[tool.ruff]\ntarget-version = "py310"\n'
    assert vc._project_table(text).strip() == 'version = "1.2.3"'
