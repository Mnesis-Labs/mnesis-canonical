"""Common abstractions for the importer framework.

Provides the abstract :class:`ImporterBase` that concrete format importers
(:mod:`.mcap_importer`, :mod:`.xrobotoolkit_importer`) subclass, plus the
:class:`ImporterRegistry` that auto-discovers them and the :class:`ImporterMetadata`
dataclass each format advertises.
"""
from __future__ import annotations

import abc
import dataclasses
import importlib
import inspect
import pkgutil
import sys
from pathlib import Path
from typing import Any

# Module-level reference to the package's __path__ so pkgutil can scan
# sibling modules.  This is set by the interpreter when the package's
# __init__.py is imported; we capture it here via the module's ``__package__``
# attribute.  Fallback to the on-disk directory when the package is not loaded.
_PACKAGE = sys.modules.get("mnesis_canonical.importers")
if _PACKAGE is not None and hasattr(_PACKAGE, "__path__"):
    _IMPORTERS_PATH: list[str] = list(_PACKAGE.__path__)  # type: ignore[union-attr]
else:
    _IMPORTERS_PATH = [
        str(Path(__file__).resolve().parent)
    ]


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ImporterMetadata:
    """Static metadata an importer advertises about the format it handles.

    Attributes:
        format_name: Short machine-readable identifier (e.g. ``"mcap"``).
        display_name: Human-readable label (e.g. ``"MCAP (ROS 2 bag)"``).
        file_extensions: File extensions this importer can open (e.g. ``[".mcap"]``).
        description: One-line summary shown in ``--help``.
    """

    format_name: str
    display_name: str
    file_extensions: tuple[str, ...]
    description: str


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class ImporterBase(abc.ABC):
    """Abstract base class for a format-specific episode importer.

    Each concrete subclass **must** set a class-level ``metadata`` attribute::

        class McapImporter(ImporterBase):
            metadata = ImporterMetadata(
                format_name="mcap",
                display_name="MCAP (ROS 2 bag)",
                file_extensions=(".mcap",),
                description="Import from MCAP (ROS 2 bag) recording files.",
            )
    """

    metadata: ImporterMetadata  # set by subclass

    @abc.abstractmethod
    def import_episode(self, path: Path, **kwargs: Any) -> list[dict]:
        """Ingest a source file and return a list of canonical frame dicts.

        Args:
            path: Path to the source file (e.g. ``.mcap`` / ``.bag`` / ``.h5``).
            **kwargs: Format-specific options (e.g. topic filter, fps).

        Returns:
            A list of frames, each a dict conforming to the Canonical Frame schema.

        Raises:
            FileNotFoundError: If *path* does not exist.
            ValueError: If the file cannot be parsed or contains unsupported data.
        """
        ...

    @abc.abstractmethod
    def describe_source(self, path: Path) -> dict:
        """Return a metadata dict describing the source file (duration, topics, …).

        Args:
            path: Path to the source file.

        Returns:
            A dict with keys such as ``"duration_s"``, ``"topic_count"``,
            ``"frame_count"``, etc.  The exact keys are format-specific.
        """
        ...


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class ImporterRegistry:
    """Auto-discoverable registry of :class:`ImporterBase` subclasses.

    Usage::

        registry = ImporterRegistry()
        mcap = registry.get("mcap")
        frames = mcap.import_episode(Path("/data/recording.mcap"))
    """

    def __init__(self) -> None:
        self._importers: dict[str, type[ImporterBase]] = {}
        self._discover()

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    @staticmethod
    def _iter_importer_modules() -> list[str]:
        """Yield fully-qualified module names under ``mnesis_canonical.importers``
        whose name does not start with ``_``."""
        # pkgutil works because mnesis_canonical.importers is a package
        return [
            f"mnesis_canonical.importers.{mod.name}"
            for mod in pkgutil.iter_modules(
                _IMPORTERS_PATH, prefix="mnesis_canonical.importers."
            )
            if not mod.name.startswith("_")
        ]

    def _discover(self) -> None:
        """Scan the ``mnesis_canonical.importers`` namespace for concrete
        :class:`ImporterBase` subclasses and register them."""
        for mod_name in self._iter_importer_modules():
            try:
                mod = importlib.import_module(mod_name)
            except (ImportError, ModuleNotFoundError):
                continue  # optional dependency not installed — skip silently
            for _, obj in inspect.getmembers(mod, inspect.isclass):
                if (
                    issubclass(obj, ImporterBase)
                    and obj is not ImporterBase
                    and hasattr(obj, "metadata")
                ):
                    self._register(obj)

    def _register(self, cls: type[ImporterBase]) -> None:
        meta = cls.metadata
        if meta.format_name in self._importers:
            return  # first-registered wins
        self._importers[meta.format_name] = cls

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, format_name: str) -> type[ImporterBase]:
        """Look up an importer class by its ``format_name``.

        Raises:
            KeyError: If no importer is registered for *format_name*.
        """
        try:
            return self._importers[format_name]
        except KeyError:
            raise KeyError(
                f"No importer registered for '{format_name}'. "
                f"Available: {', '.join(sorted(self._importers))}"
            ) from None

    def list_formats(self) -> list[ImporterMetadata]:
        """Return metadata for every registered importer."""
        return [cls.metadata for cls in self._importers.values()]

    def __contains__(self, format_name: object) -> bool:
        return format_name in self._importers

    def __len__(self) -> int:
        return len(self._importers)