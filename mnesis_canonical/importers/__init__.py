"""Ecosystem importers — third-party teleop logs → canonical episodes.

    mnesis-import xrobotoolkit teleop_log_*.pkl --out <dir>
    mnesis-import xrobotoolkit log.mcap --format airbot-mcap --out <dir>

See :mod:`.xrobotoolkit` (pickle core) and :mod:`.airbot_mcap` (second input).
"""
from __future__ import annotations

from .airbot_mcap import import_mcap
from .xrobotoolkit import import_pickle

__all__ = ["import_pickle", "import_mcap"]
