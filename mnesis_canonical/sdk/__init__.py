"""Device Adapter SDK — abstract interface + reference implementations.

Provides the :class:`DeviceAdapter` ABC that every capture-surface driver
implements, plus :class:`QuestAdapter` and :class:`RobotAdapter` skeletons
that produce validated :class:`~mnesis_canonical.schema.CanonicalFrame`
sequences from bundled example data.
"""
from __future__ import annotations

from ._adapter import DeviceAdapter, QuestAdapter, RobotAdapter

__all__ = [
    "DeviceAdapter",
    "QuestAdapter",
    "RobotAdapter",
]