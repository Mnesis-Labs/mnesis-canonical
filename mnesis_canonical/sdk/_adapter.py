"""Device adapter abstract base class and example-data-driven reference adapters.

Architecture::

                    ┌───────────────┐
                    │ DeviceAdapter │  ← ABC (open / close / read_frame)
                    └───────┬───────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
     ┌────────┴────────┐       ┌──────────┴──────────┐
     │  QuestAdapter   │       │    RobotAdapter     │  ← reference impls
     │ episode_quest   │       │   episode_robot     │     (example data)
     └─────────────────┘       └─────────────────────┘
"""
from __future__ import annotations

import abc
from collections.abc import Iterator
from pathlib import Path

from mnesis_canonical.schema import CanonicalFrame

__all__: list[str] = []  # re-exported from __init__.py


class DeviceAdapter(abc.ABC):
    """Abstract base class for capture-surface device adapters.

    Every concrete adapter **must** implement :meth:`open`, :meth:`close`,
    and :meth:`read_frame`.  Calling any unimplemented abstract method on a
    subclass that does not override it raises :exc:`TypeError` at
    instantiation time (standard Python ABC behaviour).

    Supports the context-manager protocol::

        with MyAdapter() as dev:
            frame = dev.read_frame()
    """

    @abc.abstractmethod
    def open(self) -> None:
        """Open / initialise the device connection."""

    @abc.abstractmethod
    def close(self) -> None:
        """Close the device connection and release resources."""

    @abc.abstractmethod
    def read_frame(self) -> CanonicalFrame:
        """Read the next available :class:`CanonicalFrame`.

        Returns:
            The next frame from the device stream.

        Raises:
            StopIteration: when no more frames are available.
        """

    def __iter__(self) -> Iterator[CanonicalFrame]:
        return self

    def __next__(self) -> CanonicalFrame:
        return self.read_frame()

    def __enter__(self) -> DeviceAdapter:
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class _ExampleAdapter(DeviceAdapter):
    """Base for reference adapters that replay bundled example data."""

    def __init__(self, source: str | Path | None = None) -> None:
        if source is None:
            source = self._default_source()
        self._source = Path(source)
        self._frames: list[CanonicalFrame] = []
        self._pos: int = 0

    @classmethod
    @abc.abstractmethod
    def _default_source(cls) -> Path:
        """Return the default path to the relevant example JSONL file."""

    def open(self) -> None:
        from mnesis_canonical.io import read_jsonl

        raw = read_jsonl(self._source)
        self._frames = [CanonicalFrame.from_dict(d) for d in raw]
        self._pos = 0

    def close(self) -> None:
        self._frames = []
        self._pos = 0

    def read_frame(self) -> CanonicalFrame:
        if self._pos >= len(self._frames):
            raise StopIteration("No more frames available")
        frame = self._frames[self._pos]
        self._pos += 1
        return frame


_EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"


class QuestAdapter(_ExampleAdapter):
    """Reference adapter that replays the ``episode_quest`` example data.

    The adapter reads from the bundled ``examples/episode_quest/data.jsonl``
    by default.  Usage::

        adapter = QuestAdapter()
        adapter.open()
        frame = adapter.read_frame()  # CanonicalFrame
        adapter.close()

    Or via context manager / iteration::

        with QuestAdapter() as dev:
            for frame in dev:
                print(frame.index)
    """

    source_device = "quest"

    @classmethod
    def _default_source(cls) -> Path:
        return _EXAMPLES_DIR / "episode_quest" / "data.jsonl"


class RobotAdapter(_ExampleAdapter):
    """Reference adapter that replays the ``episode_robot`` example data.

    The adapter reads from the bundled ``examples/episode_robot/data.jsonl``
    by default.  Usage::

        with RobotAdapter() as dev:
            frame = dev.read_frame()
    """

    source_device = "robot"

    @classmethod
    def _default_source(cls) -> Path:
        return _EXAMPLES_DIR / "episode_robot" / "data.jsonl"