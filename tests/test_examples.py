"""Every shipped example episode must validate, across all capture surfaces (C4)."""
from __future__ import annotations

from pathlib import Path

import pytest

from mnesis_canonical import (
    DEVICES,
    MODALITIES,
    read_jsonl,
    validate_frames,
)

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
EPISODES = sorted(EXAMPLES_DIR.glob("*/data.jsonl"))


def test_examples_discovered():
    # phone (episode_0), quest, robot — the three capture surfaces in the sprint.
    names = {p.parent.name for p in EPISODES}
    assert {"episode_0", "episode_quest", "episode_robot"} <= names


@pytest.mark.parametrize("path", EPISODES, ids=lambda p: p.parent.name)
def test_example_episode_strict_valid(path):
    report = validate_frames(read_jsonl(path), strict_vocab=True)
    assert report.ok, report.errors


def test_examples_cover_multiple_surfaces():
    devices, modalities = set(), set()
    for path in EPISODES:
        for frame in read_jsonl(path):
            devices.add(frame["source.device"])
            modalities.add(frame["source.modality"])
    assert {"phone", "quest", "robot"} <= devices
    assert {"ego_human", "teleop", "robot_replay"} <= modalities
    # Anything used in the examples must be in the frozen vocab.
    assert devices <= set(DEVICES)
    assert modalities <= set(MODALITIES)
