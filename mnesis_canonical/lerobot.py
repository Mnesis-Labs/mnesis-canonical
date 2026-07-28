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


def _non_nullable_keys() -> frozenset[str]:
    """Schema-declared keys whose type does **not** admit ``null`` as a value.

    This is the only thing that distinguishes the two kinds of "nothing" that the
    columnar form collapses together (see :func:`from_lerobot`).  Derived from the
    schema rather than hand-listed, so a future field that gains or loses
    ``"null"`` in its type is picked up automatically instead of silently
    diverging from a stale constant.
    """
    from .validate import load_json_schema

    def _admits_null(spec: dict) -> bool:
        t = spec.get("type")
        if isinstance(t, list):
            return "null" in t
        if t == "null":
            return True
        for branch in ("anyOf", "oneOf"):
            if branch in spec:
                return any(_admits_null(x) for x in spec[branch])
        return False

    props = load_json_schema().get("properties", {})
    return frozenset(k for k, v in props.items() if not _admits_null(v))


def from_lerobot(columns: dict[str, list]) -> list[dict]:
    """Inverse of :func:`to_lerobot`: transpose columns back into frame dicts.

    The columnar form collapses **two different kinds of "nothing"** into the same
    ``None`` cell:

    * the frame never carried the key (an untracked hand omits
      ``observation.hand.<side>`` — SPEC §Conventions "Absent means unknown"), and
    * the frame carried the key with an explicit ``null`` value
      (``spatial_anchor_id`` is typed ``str | null``).

    Emitting every column into every frame — the previous behaviour — fabricates
    the first kind: a frame that never had ``observation.hand.right`` came back
    carrying ``observation.hand.right: None``, which both breaks the round-trip
    and violates the very rule ``examples/episode_hands`` ships to demonstrate
    (``tests/test_hand.py::test_example_omits_the_untracked_hand``).

    The schema already records which keys legitimately hold ``null``, so that is
    what decides — and the rule is deliberately narrow: ``None`` is dropped only
    for keys the schema **declares and marks non-nullable**.  Keys the schema does
    not know (vendor extensions, ad-hoc columns) are carried through untouched:
    without a schema there is no basis to rule their ``null`` illegitimate, and
    guessing would silently discard a producer's data.
    """
    keys = list(columns.keys())
    n = len(next(iter(columns.values()))) if columns else 0
    drop_none_for = _non_nullable_keys()
    return [
        {
            key: columns[key][i]
            for key in keys
            if columns[key][i] is not None or key not in drop_none_for
        }
        for i in range(n)
    ]
