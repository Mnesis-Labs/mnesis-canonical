"""Importer registry — single source of truth for ``mnesis-import list``.

Each entry declares an importer name, its supported input formats, and a
short description. The CLI parser and the ``list`` subcommand both read from
this registry so they stay in sync.

Add a new importer here when wiring it into ``__main__.py``.
"""
from __future__ import annotations

REGISTRY: list[dict] = [
    {
        "name": "xrobotoolkit",
        "help": "Import an XRoboToolkit pickle (or airbot .mcap via --format).",
        "formats": [
            {"name": "pickle", "description": "XRoboToolkit teleop pickle (.pkl)"},
            {"name": "airbot-mcap", "description": "AIRBOT MCAP log (.mcap)"},
        ],
    },
]