#!/usr/bin/env python
"""§1 of ``docs/RELEASE_CHECKLIST_v1.0.md``: one version number, three places.

The package version is written down three times and nothing used to keep the
copies together (#76): ``pyproject.toml`` sat at ``0.2.0`` while ``__version__``
said ``0.5.0`` and the ``CHANGELOG.md`` preamble said ``0.3.0``.  A wheel built
from that tree **installs as one version and reports another**, so a consumer
gets a different answer depending on which one it asks.

This module is the single comparison.  ``tests/test_version_consistency.py``
imports it and ``scripts/release_check.py`` runs it as §1, so the drift cannot
come back through either door.

Deliberately a regex over file text rather than ``tomllib`` + ``import
mnesis_canonical``: ``tomllib`` is 3.11+ (the package supports 3.10) and reading
the strings means the check works on a tree that does not even import.

    python scripts/version_check.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PYPROJECT = REPO_ROOT / "pyproject.toml"
INIT = REPO_ROOT / "mnesis_canonical" / "__init__.py"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

_PYPROJECT_VERSION = re.compile(r"^version\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE)
_DUNDER_VERSION = re.compile(r"^__version__\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE)
# The preamble line that names the current package version, e.g. `**Package 0.5.0**`.
_CHANGELOG_VERSION = re.compile(r"\*\*Package\s+([0-9][0-9A-Za-z.\-+]*)\*\*")


def _project_table(text: str) -> str:
    """Return the body of the ``[project]`` table only.

    Scoping matters: ``[tool.ruff] target-version`` also ends in ``version``, and a
    sloppier match would happily compare against ``py310``.
    """
    lines: list[str] = []
    inside = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            inside = stripped == "[project]"
            continue
        if inside:
            lines.append(line)
    return "\n".join(lines)


def _extract(pattern: re.Pattern[str], text: str, what: str) -> str:
    match = pattern.search(text)
    if match is None:
        raise AssertionError(f"could not find {what}")
    return match.group(1)


def read_pyproject_version(path: Path = PYPROJECT) -> str:
    """``[project] version`` from ``pyproject.toml``."""
    table = _project_table(path.read_text(encoding="utf-8"))
    return _extract(_PYPROJECT_VERSION, table, f"[project] version in {path.name}")


def read_dunder_version(path: Path = INIT) -> str:
    """``__version__`` from ``mnesis_canonical/__init__.py`` (read, not imported)."""
    return _extract(_DUNDER_VERSION, path.read_text(encoding="utf-8"),
                    f"__version__ in {path.name}")


def read_changelog_version(path: Path = CHANGELOG) -> str:
    """The ``**Package x.y.z**`` version named in the ``CHANGELOG.md`` preamble."""
    return _extract(_CHANGELOG_VERSION, path.read_text(encoding="utf-8"),
                    f"**Package x.y.z** in {path.name}")


def check() -> list[str]:
    """Return one problem line per disagreeing source; empty list means consistent."""
    found = {
        "pyproject.toml [project] version": read_pyproject_version(),
        "mnesis_canonical/__init__.py __version__": read_dunder_version(),
        "CHANGELOG.md **Package x.y.z**": read_changelog_version(),
    }
    if len(set(found.values())) == 1:
        return []
    return [f"{where} = {version!r}" for where, version in found.items()]


def main(argv: list[str] | None = None) -> int:
    problems = check()
    if problems:
        print("VERSION MISMATCH — these must all be the same string:")
        for line in problems:
            print(f"  {line}")
        return 1
    print(f"version consistent: {read_dunder_version()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
