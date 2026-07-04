"""LeRobot interop — columnar <-> Canonical frame conversion.

LeRobot datasets are *columnar* (one aligned list per feature). The Canonical
Schema's flat, dotted keys map 1:1 onto LeRobot dataset features, so conversion
is a pure transpose with no renaming or unit change (SPEC §Compatibility / 4c
DATA5). The LeRobot-native features are carried verbatim; the extra canonical
columns (head_pose_SE3, t_hw_ns, source.device, ...) ride along losslessly so a
round-trip is exact.
"""
from __future__ import annotations

from .schema import NULLABLE_KEYS, REQUIRED_KEYS

# LeRobot-native features that map 1:1 onto canonical keys (no renaming).
LEROBOT_FEATURES = (
    "observation.state",
    "action",
    "timestamp",
    "episode_index",
    "frame_index",
    "index",
    "task_index",
)


def to_lerobot(frames: list[dict]) -> dict[str, list]:
    """Transpose canonical frames into a LeRobot-style columnar dict.

    Each canonical key becomes a column (list) aligned by row. The LeRobot-native
    features (:data:`LEROBOT_FEATURES`) map 1:1; extra canonical columns ride
    along. Optional keys (e.g. ``spatial_anchor_id``) only become a column when
    at least one frame carries them, so the round-trip stays exact.
    """
    columns_present = list(REQUIRED_KEYS) + [
        key for key in NULLABLE_KEYS if any(key in frame for frame in frames)
    ]
    return {key: [frame.get(key) for frame in frames] for key in columns_present}


def from_lerobot(columns: dict[str, list]) -> list[dict]:
    """Inverse of :func:`to_lerobot`: transpose columns back into frame dicts.

    Only recognised canonical columns are emitted (in canonical order); any extra
    non-canonical columns are ignored.
    """
    keys = [key for key in (REQUIRED_KEYS + NULLABLE_KEYS) if key in columns]
    n = len(next(iter(columns.values()))) if columns else 0
    return [{key: columns[key][i] for key in keys} for i in range(n)]
