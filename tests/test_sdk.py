"""Tests for the DeviceAdapter SDK — ABC contract + reference implementations."""
from __future__ import annotations

from pathlib import Path

import pytest

from mnesis_canonical import validate_frame
from mnesis_canonical.schema import CanonicalFrame
from mnesis_canonical.sdk import DeviceAdapter, QuestAdapter, RobotAdapter

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


# ── ABC contract ───────────────────────────────────────────────────────────────


def test_incomplete_subclass_cannot_be_instantiated():
    """DeviceAdapter is an ABC — subclasses must implement all abstract methods."""

    class Incomplete(DeviceAdapter):
        pass

    with pytest.raises(TypeError):
        Incomplete()  # can't instantiate without override


def test_incomplete_subclass_partial_cannot_be_instantiated():
    """Even a single unimplemented abstract method prevents instantiation."""

    class Partial(DeviceAdapter):
        def open(self) -> None:
            pass

        def close(self) -> None:
            pass

    with pytest.raises(TypeError):
        Partial()


# ── QuestAdapter ───────────────────────────────────────────────────────────────


def test_quest_adapter_importable():
    from mnesis_canonical.sdk import QuestAdapter

    assert issubclass(QuestAdapter, DeviceAdapter)


def test_quest_adapter_reads_frames():
    qa = QuestAdapter()
    qa.open()
    frames: list[CanonicalFrame] = []
    try:
        while True:
            frames.append(qa.read_frame())
    except StopIteration:
        pass
    qa.close()

    assert len(frames) == 2
    for f in frames:
        assert isinstance(f, CanonicalFrame)
        assert f.source_device == "quest"


def test_quest_adapter_frames_validate():
    qa = QuestAdapter()
    qa.open()
    try:
        while True:
            f = qa.read_frame()
            errs = validate_frame(f.to_dict())
            assert not errs, f"Frame {f.index} errors: {errs}"
    except StopIteration:
        pass
    qa.close()


def test_quest_adapter_stop_iteration():
    qa = QuestAdapter()
    qa.open()
    try:
        while True:
            qa.read_frame()
    except StopIteration:
        pass
    # No more frames
    with pytest.raises(StopIteration):
        qa.read_frame()
    qa.close()


def test_quest_adapter_close_resets():
    qa = QuestAdapter()
    qa.open()
    try:
        while True:
            qa.read_frame()
    except StopIteration:
        pass
    qa.close()
    # After close, reading should still raise after re-open
    qa.open()
    f = qa.read_frame()
    assert isinstance(f, CanonicalFrame)
    qa.close()


def test_quest_adapter_context_manager():
    with QuestAdapter() as qa:
        f = qa.read_frame()
        assert isinstance(f, CanonicalFrame)
        assert f.source_device == "quest"


def test_quest_adapter_iterator():
    with QuestAdapter() as qa:
        frames = list(qa)
        assert len(frames) == 2
        for f in frames:
            assert isinstance(f, CanonicalFrame)


def test_quest_adapter_custom_source():
    custom = EXAMPLES_DIR / "episode_quest" / "data.jsonl"
    qa = QuestAdapter(source=custom)
    with qa:
        frames = list(qa)
        assert len(frames) == 2
        assert frames[0].source_device == "quest"


# ── RobotAdapter ───────────────────────────────────────────────────────────────


def test_robot_adapter_importable():
    from mnesis_canonical.sdk import RobotAdapter

    assert issubclass(RobotAdapter, DeviceAdapter)


def test_robot_adapter_reads_frames():
    ra = RobotAdapter()
    ra.open()
    frames: list[CanonicalFrame] = []
    try:
        while True:
            frames.append(ra.read_frame())
    except StopIteration:
        pass
    ra.close()

    assert len(frames) == 2
    for f in frames:
        assert isinstance(f, CanonicalFrame)
        assert f.source_device == "robot"


def test_robot_adapter_frames_validate():
    ra = RobotAdapter()
    ra.open()
    try:
        while True:
            f = ra.read_frame()
            errs = validate_frame(f.to_dict())
            assert not errs, f"Frame {f.index} errors: {errs}"
    except StopIteration:
        pass
    ra.close()


def test_robot_adapter_context_manager():
    with RobotAdapter() as ra:
        f = ra.read_frame()
        assert isinstance(f, CanonicalFrame)
        assert f.source_device == "robot"


def test_robot_adapter_iterator():
    with RobotAdapter() as ra:
        frames = list(ra)
        assert len(frames) == 2
        for f in frames:
            assert isinstance(f, CanonicalFrame)


def test_robot_adapter_stop_iteration():
    ra = RobotAdapter()
    ra.open()
    with pytest.raises(StopIteration):
        while True:
            ra.read_frame()
    ra.close()


# ── Edge cases ─────────────────────────────────────────────────────────────────


def test_source_default_is_resolved():
    """Default source paths should point to real files."""
    qa = QuestAdapter()
    assert qa._source.exists(), f"Quest source not found: {qa._source}"
    ra = RobotAdapter()
    assert ra._source.exists(), f"Robot source not found: {ra._source}"


def test_missing_custom_source_raises():
    with pytest.raises(FileNotFoundError):
        qa = QuestAdapter(source="/nonexistent/path/data.jsonl")
        qa.open()