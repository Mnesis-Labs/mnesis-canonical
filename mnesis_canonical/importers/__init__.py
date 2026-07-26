"""Mnesis Canonical Importers — multi-format episode ingestion framework.

``python -m mnesis_canonical.importers --help`` to see available subcommands.

Importers discoverable via the ``ImporterRegistry`` — each format registers a
subclass of :class:`ImporterBase` (see :mod:`._common`) and is wired into the
CLI automatically.
"""

from ._common import ImporterBase, ImporterMetadata, ImporterRegistry

__all__ = [
    "ImporterBase",
    "ImporterMetadata",
    "ImporterRegistry",
]