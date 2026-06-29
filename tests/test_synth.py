"""Tests for the deterministic synthetic episode generator (D1)."""
from __future__ import annotations

import pytest

from mnesis_canonical import (
    DEVICES,
    MODALITIES,
    demo_episodes,
    synth_episode,
    validate_frames,
)


def test_synth_requires_two_frames():
    with pytest.raises(ValueError):
        synth_episode(
            episode_index=0, n_frames=1, device="phone", modality="ego_human", shape="arc"
        )


def test_demo_episodes_are_strictly_valid():
    eps = demo_episodes()
    assert set(eps) == {"episode_phone", "episode_quest", "episode_robot"}
    for name, frames in eps.items():
        report = validate_frames(frames, strict_vocab=True)
        assert report.ok, (name, report.errors)
        # frame_index is 0..n-1 and strictly increasing.
        assert [f["frame_index"] for f in frames] == list(range(len(frames)))
        # vocab stays inside the frozen sets.
        assert frames[0]["source.device"] in DEVICES
        assert frames[0]["source.modality"] in MODALITIES


def test_demo_episodes_cover_three_surfaces():
    eps = demo_episodes()
    devices = {frames[0]["source.device"] for frames in eps.values()}
    assert devices == {"phone", "quest", "robot"}
    # Non-trivial trajectories (so the plots aren't two dots).
    assert all(len(frames) >= 60 for frames in eps.values())


def test_synth_is_deterministic():
    assert demo_episodes() == demo_episodes()
