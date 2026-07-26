"""Ecosystem importers — third-party teleop logs → canonical episodes (second input).

    mnesis-import xrobotoolkit log.pkl --out <dir>

See :mod:`.xrobotoolkit` for the XRoboToolkit pickle path.
"""
from __future__ import annotations

from .xrobotoolkit import import_pickle

__all__ = ["import_pickle"]