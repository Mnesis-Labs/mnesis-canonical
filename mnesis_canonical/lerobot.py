"""LeRobot interop — columnar <-> Canonical frame conversion.

LeRobot datasets are *columnar* (one aligned list per feature). The Canonical
Schema's flat, dotted keys map 1:1 onto LeRobot dataset features, so conversion
is a pure transpose with no renaming or unit change (SPEC §Compatibility / 4c
DATA5). The LeRobot-native features are carried verbatim; the extra canonical
columns (head_pose_SE3, t_hw_ns, source.device, ...) ride along losslessly so a
round-trip is exact.
"""
from __future__ import annotations

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


def _all_keys(frames: list[dict]) -> list[str]:
    """Return all unique keys present across *frames*, preserving insertion order."""
    seen: set[str] = set()
    order: list[str] = []
    for frame in frames:
        for key in frame:
            if key not in seen:
                seen.add(key)
                order.append(key)
    return order


def to_lerobot(frames: list[dict]) -> dict[str, list]:
    """Transpose canonical frames into a LeRobot-style columnar dict.

    Every key present in at least one frame becomes a column (list) aligned by
    row.  The LeRobot-native features (:data:`LEROBOT_FEATURES`) map 1:1; extra
    canonical columns ride along.  Optional keys that no frame carries are
    omitted, so the round-trip stays exact.
    """
    columns_present = _all_keys(frames)
    return {key: [frame.get(key) for frame in frames] for key in columns_present}


def from_lerobot(columns: dict[str, list]) -> list[dict]:
    """Inverse of :func:`to_lerobot`: transpose columns back into frame dicts.

    Every column in the input is emitted as a key in each frame — no filtering
    to a static allowlist — so the round-trip is exact.

    Keys whose value is ``None`` for a given frame are omitted, per the
    ``missing = unknown`` rule (no in-band sentinels): a frame that originally
    lacked a key does not get it back as ``None``.  This is safe because
    ``None`` is never a semantically meaningful value for a canonical field
    that was genuinely absent — fields that accept ``None`` (e.g.
    ``spatial_anchor_id``) treat ``None`` and absent identically.
    """
    keys = list(columns.keys())
    n = len(next(iter(columns.values()))) if columns else 0
    return [
        {key: columns[key][i] for key in keys if columns[key][i] is not None}
        for i in range(n)
    ]
