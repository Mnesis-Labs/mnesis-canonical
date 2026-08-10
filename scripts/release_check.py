#!/usr/bin/env python
"""Automate §1–§6 of ``docs/RELEASE_CHECKLIST_v1.0.md``.

Runs every machine-executable checklist item and exits non-zero if any fails, so
"forgot to run one of the steps" stops being possible.  §1's version-string half
is a comparison of three strings, so it runs here too (#76 — it used to be a
reminder and the strings drifted).  Only §1's CHANGELOG rollover and §7's tag
push stay manual — §8 (GitHub Release + PyPI) is what the tag push triggers
(#109); the script prints a reminder for the rest.

    python scripts/release_check.py [--only SECTION] [--strict]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"

MANUAL_REMINDER = ("not automated: §1 CHANGELOG [Unreleased] rollover · "
                   "§7 git tag & push  |  §8 GitHub Release + PyPI runs itself "
                   "from the tag (.github/workflows/release.yml)")

VERSION_CHECK = REPO_ROOT / "scripts" / "version_check.py"


@dataclass(frozen=True)
class Step:
    """One command from the checklist.

    ``requires``  executable that must be on PATH for this step to run
    ``optional``  a missing ``requires`` executable is a SKIP, not a FAIL
    ``advisory``  a non-zero exit is a SKIP, not a FAIL (unless ``--strict``)
    """

    label: str
    argv: list[str]
    requires: str | None = None
    optional: bool = False
    advisory: bool = False
    note: str = ""


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    steps: list[Step] = field(default_factory=list)


_PY = [sys.executable]


def build_sections() -> list[Section]:
    return [
        Section("version", "§1 Version consistency", [
            Step("python scripts/version_check.py", [*_PY, str(VERSION_CHECK)]),
        ]),
        Section("contracts", "§2 Contracts integrity", [
            Step("python -m mnesis_canonical.contracts_check",
                 [*_PY, "-m", "mnesis_canonical.contracts_check"]),
        ]),
        Section("embodiments", "§3 Embodiment registry", [
            Step("python -m mnesis_canonical.embodiment_check",
                 [*_PY, "-m", "mnesis_canonical.embodiment_check"]),
        ]),
        Section("lint", "§4 Lint & type check", [
            Step("ruff check .", ["ruff", "check", "."], requires="ruff"),
            # pyright is optional (skipped when not installed) but NOT advisory —
            # when installed, type errors are a hard gate.
            Step("pyright .", ["pyright", "."], requires="pyright", optional=True),
        ]),
        Section("tests", "§5 Tests", [
            Step("pytest -q", [*_PY, "-m", "pytest", "-q"]),
        ]),
        Section("smoke", "§6 Manual smoke tests", [
            Step("python -m mnesis_canonical --help", [*_PY, "-m", "mnesis_canonical", "--help"]),
            Step("python -m mnesis_canonical validate examples/episode_0/data.jsonl",
                 [*_PY, "-m", "mnesis_canonical", "validate", "examples/episode_0/data.jsonl"]),
            Step("python -m mnesis_canonical.importers --help",
                 [*_PY, "-m", "mnesis_canonical.importers", "--help"]),
            # `list` landed in #63 — no longer advisory, a broken registry is a gate.
            Step("python -m mnesis_canonical.importers list",
                 [*_PY, "-m", "mnesis_canonical.importers", "list"]),
        ]),
    ]


def _run(step: Step) -> tuple[int, str]:
    """Execute ``step`` and return (returncode, combined output).

    Seam for tests: monkeypatch this instead of breaking real repo files.
    """
    proc = subprocess.run(
        step.argv, cwd=REPO_ROOT, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def execute_step(step: Step, strict: bool = False) -> tuple[str, str]:
    """Return ``(status, detail)`` for a single step."""
    if step.requires and shutil.which(step.requires) is None:
        detail = f"{step.requires} not on PATH"
        return (FAIL, detail) if not step.optional else (SKIP, detail)
    code, output = _run(step)
    if code == 0:
        return PASS, ""
    if step.advisory and not strict:
        return SKIP, step.note or f"exit {code} (advisory)"
    return FAIL, output.strip() or f"exit {code}"


def run(sections: list[Section], strict: bool = False) -> int:
    passed = failed = skipped = 0
    failed_sections: list[str] = []

    for section in sections:
        print(f"\n=== {section.title} ({section.key}) ===")
        for step in section.steps:
            status, detail = execute_step(step, strict=strict)
            print(f"  [{status}] {step.label}" + (f" — {detail.splitlines()[0]}"
                                                  if status == SKIP and detail else ""))
            if status == PASS:
                passed += 1
            elif status == SKIP:
                skipped += 1
            else:
                failed += 1
                if section.key not in failed_sections:
                    failed_sections.append(section.key)
                for line in detail.splitlines():
                    print(f"        {line}")

    print()
    if failed_sections:
        print(f"FAILED sections: {', '.join(failed_sections)}")
    print(MANUAL_REMINDER)
    print(f"RELEASE_CHECK summary passed={passed} failed={failed} skipped={skipped}")
    return 1 if failed else 0


def build_parser(keys: list[str]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python scripts/release_check.py",
        description="Run §1–§6 of docs/RELEASE_CHECKLIST_v1.0.md.",
    )
    parser.add_argument("--only", choices=keys, action="append", metavar="SECTION",
                        help=f"Run only this section (repeatable). One of: {', '.join(keys)}.")
    parser.add_argument("--strict", action="store_true",
                        help="Treat advisory steps (pyright, unimplemented CLI) as gates.")
    return parser


def main(argv: list[str] | None = None) -> int:
    sections = build_sections()
    args = build_parser([s.key for s in sections]).parse_args(argv)
    if args.only:
        sections = [s for s in sections if s.key in args.only]
    return run(sections, strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())