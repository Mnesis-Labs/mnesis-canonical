"""Integration test: wheel-installed package must serve the loader API.

Builds a wheel, installs it into a temporary venv, and verifies that
``list_embodiments()`` returns 5 entries from a non-source-tree directory.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

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
    code = "import mnesis_canonical as m; print(len(m.list_embodiments()))"
    result = subprocess.run(
        [str(python), "-c", code],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert result.returncode == 0, f"Loader failed:\n{result.stderr}"
    count = int(result.stdout.strip())
    assert count == 5, f"Expected 5 embodiments, got {count}"