"""Tests for trajectory visualisation (D3). Skipped if matplotlib is absent."""
from __future__ import annotations

import pytest

pytest.importorskip("matplotlib")

from mnesis_canonical import demo_episodes, plot_trajectories  # noqa: E402


def test_plot_trajectories_writes_png(tmp_path):
    out = plot_trajectories(demo_episodes(), tmp_path / "sub" / "trajectories.png")
    assert out.exists()
    assert out.stat().st_size > 1000  # a real PNG, not an empty file
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic
