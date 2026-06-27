"""LeRobot interop: Canonical frames <-> LeRobot-style columnar dict.

LeRobot datasets are columnar (one list per feature). The Canonical Schema is
already LeRobot-native (flat dotted keys), so this is a transpose + a stable
column ordering. Keeps Mnesis data feedable to LeRobot / Isaac / GR00T pipelines
without re-labeling (SPEC §Compatibility, `4c` DATA5).
"""
from __future__ import annotations

# Columns we export to LeRobot, in stable order.
LEROBOT_COLUMNS = (
    "index",
    "episode_index",
    "task_index",
    "frame_index",
    "timestamp",
    "observation.state",
    "action",
    "observation.images.ego",
)


def to_lerobot(frames: list[dict]) -> dict[str, list]:
    """Transpose Canonical frames -> {column: [values...]} (LeRobot-style)."""
    columns: dict[str, list] = {col: [] for col in LEROBOT_COLUMNS}
    for f in frames:
        for col in LEROBOT_COLUMNS:
            columns[col].append(f[col])
    return columns


def from_lerobot(columns: dict[str, list]) -> list[dict]:
    """Inverse of to_lerobot (only the LeRobot columns; lossy for Mnesis-only fields)."""
    n = len(columns[LEROBOT_COLUMNS[0]]) if columns.get(LEROBOT_COLUMNS[0]) else 0
    return [{col: columns[col][i] for col in LEROBOT_COLUMNS} for i in range(n)]
