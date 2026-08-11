"""Integration test: wheel-installed package must serve the loader API.

Builds a wheel, installs it into a temporary venv, and verifies that
``list_embodiments()`` returns 5 entries from a non-source-tree directory — and
that the *installed distribution* version matches ``__version__`` (#76: the two
disagreed, so ``pip install`` gave 0.2.0 while the package reported 0.5.0).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import mnesis_canonical

WHEEL_DIR = Path(__file__).resolve().parent.parent


@pytest.mark.slow
def test_wheel_install_loader(tmp_path: Path) -> None:
    """Build a wheel, install it, and verify the loader works outside source."""
    # Build wheel
    result = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", str(WHEEL_DIR)],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert result.returncode == 0, f"pip wheel failed:\n{result.stderr}"
    # Locate the .whl file
    whl_files = list(tmp_path.glob("mnesis_canonical-*.whl"))
    assert len(whl_files) == 1, f"Expected one wheel, found {whl_files}"
    whl = whl_files[0]
    expected = mnesis_canonical.__version__
    assert whl.name.startswith(f"mnesis_canonical-{expected}-"), (
        f"wheel built as {whl.name}, but the package reports {expected}"
    )

    # Create a temp venv and install the wheel
    venv = tmp_path / "venv"
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv)],
        check=True, capture_output=True,
    )
    pip = venv / "bin" / "pip"
    if not pip.exists():
        pip = venv / "Scripts" / "pip.exe"
    subprocess.run(
        [str(pip), "install", str(whl)],
        check=True, capture_output=True,
    )

    # Run the loader from a directory outside the source tree
    python = venv / "bin" / "python"
    if not python.exists():
        python = venv / "Scripts" / "python.exe"
    code = (
        "import mnesis_canonical as m; "
        "from importlib.metadata import version; "
        "print(len(m.list_embodiments())); print(m.__version__); "
        "print(version('mnesis-canonical'))"
    )
    result = subprocess.run(
        [str(python), "-c", code],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert result.returncode == 0, f"Loader failed:\n{result.stderr}"
    count, reported, installed = result.stdout.split()
    assert int(count) == 6, f"Expected 6 embodiments, got {count}"
    # What pip installed it as vs. what the package says about itself: #76's bug
    # was exactly these two disagreeing, and the old assertion never looked.
    assert installed == reported == expected, (
        f"dist version {installed!r} != __version__ {reported!r} (source: {expected!r})"
    )

    # The C12 class_id value domain is read from bundled taxonomy data at
    # validation time — if it does not ship in the wheel, every label a consumer
    # validates fails on class_id rather than on anything real.
    code = (
        "import mnesis_canonical as m; "
        "print(len(m.object_class_ids()), 'cup' in m.object_class_ids())"
    )
    result = subprocess.run(
        [str(python), "-c", code],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert result.returncode == 0, f"Taxonomy loader failed:\n{result.stderr}"
    count, has_cup = result.stdout.split()
    assert int(count) > 0 and has_cup == "True", result.stdout
