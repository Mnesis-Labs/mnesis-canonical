"""Ecosystem importers — third-party teleop logs → canonical episodes (second input).

    mnesis-import xrobotoolkit log.pkl --out <dir>
    mnesis-import xrobotoolkit log.mcap --format airbot-mcap --out <dir>

See :mod:`.airbot_mcap` for the airbot MCAP smoke path and :mod:`.xrobotoolkit`
for the XRoboToolkit pickle path.
"""
from __future__ import annotations

from .airbot_mcap import import_mcap
from .xrobotoolkit import import_pickle

__all__ = ["import_mcap", "import_pickle"]