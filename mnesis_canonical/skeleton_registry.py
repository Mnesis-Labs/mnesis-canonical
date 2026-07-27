"""Skeleton Layout Registry loader API — the topology table behind variable-length
keypoint vectors.

A canonical frame carries hand keypoints as a **variable-length** vector plus a
``observation.hand.layout`` id; this module resolves that id to the layout entry
that says how many joints the vector has and what each index means.  Same shape
as :mod:`mnesis_canonical.embodiment_registry` (which resolves ``embodiment_id``
to the ``joint_names`` behind ``observation.state``) — deliberately, so the
standard has one mechanism for "the length of this vector is declared elsewhere"
instead of two.

Why not a fixed length: a hard-coded ``float[63]`` (MediaPipe's 21 landmarks × 3)
only works while every producer is MediaPipe.  WebXR Hand Input carries 25 joints
and OpenXR 26, both with per-joint orientation, and skeleton-level retargeting
consumes exactly that orientation.  See SPEC.md §Hand keypoints / C11.

Reads from the bundled package data (``mnesis_canonical/skeletons/``), so it
works from source and from a pip-installed wheel alike.
"""
from __future__ import annotations

import importlib.resources as _resources
import importlib.resources.abc as _resources_abc
import json
from pathlib import Path

_PACKAGE = "mnesis_canonical.skeletons"
_SCHEMA_FILE = "skeleton.schema.json"


def _read_traversable(ref: _resources_abc.Traversable) -> dict:
    """Read a JSON file from a Traversable (works for both file-system and zip/egg)."""
    return json.loads(ref.read_text(encoding="utf-8"))


def _skeleton_paths() -> list[_resources_abc.Traversable]:
    """Return sorted Traversables for the skeleton layout JSON files."""
    try:
        ref = _resources.files(_PACKAGE)
    except (TypeError, AttributeError, ModuleNotFoundError):
        ref = Path(__file__).resolve().parent / "skeletons"
    return sorted(
        (
            p for p in ref.iterdir()
            if p.name.endswith(".json") and p.name != _SCHEMA_FILE
        ),
        key=lambda t: t.name,
    )


def _load_schema() -> dict:
    """Load the bundled skeleton layout JSON Schema."""
    try:
        ref = _resources.files(_PACKAGE) / _SCHEMA_FILE
        return _read_traversable(ref)
    except (TypeError, AttributeError, ModuleNotFoundError):
        ref = Path(__file__).resolve().parent / "skeletons" / _SCHEMA_FILE
        return json.loads(ref.read_text(encoding="utf-8"))


def list_skeletons(*, kind: str | None = None) -> list[dict]:
    """Return all skeleton layout entries as a list of dicts.

    Args:
        kind: Optional filter on the ``kind`` field (``"hand"`` / ``"body"``).
    """
    entries = [_read_traversable(p) for p in _skeleton_paths()]
    if kind is not None:
        entries = [e for e in entries if e.get("kind") == kind]
    return entries


def list_skeleton_ids(*, kind: str | None = None) -> list[str]:
    """Return the sorted list of registered skeleton layout ids."""
    return sorted(e["id"] for e in list_skeletons(kind=kind))


def load_skeleton(layout_id: str, *, validate: bool = False) -> dict:
    """Load a single skeleton layout entry by its ``id`` field.

    Args:
        layout_id: The ``id`` value (e.g. ``"mediapipe_hand_21"``).
        validate: If ``True``, validate against the bundled JSON Schema
            (requires the optional ``jsonschema`` dependency).

    Raises:
        LookupError: If no layout with the given id is registered.
        RuntimeError: If ``validate=True`` and the entry fails schema validation.
    """
    for p in _skeleton_paths():
        data = _read_traversable(p)
        if data.get("id") == layout_id:
            if validate:
                try:
                    import jsonschema
                except ImportError as e:  # pragma: no cover - exercised only without extra
                    raise RuntimeError(
                        "load_skeleton(validate=True) requires the optional "
                        "'jsonschema' dependency; install with: "
                        "pip install mnesis-canonical[jsonschema]"
                    ) from e
                validator = jsonschema.Draft202012Validator(_load_schema())
                errs = [
                    err.message
                    for err in sorted(validator.iter_errors(data), key=str)
                ]
                if errs:
                    raise RuntimeError(
                        f"Skeleton layout '{layout_id}' failed schema validation: {errs}"
                    )
            return data
    raise LookupError(f"Skeleton layout '{layout_id}' not found in registry")


def joint_count(layout_id: str) -> int:
    """Return the joint count K for a layout id.

    A position vector for the layout has exactly ``3 * K`` numbers and an
    orientation vector exactly ``4 * K`` — this is what
    :func:`mnesis_canonical.validate_frame` checks hand keypoints against.

    Raises:
        LookupError: If the layout id is not registered.
    """
    return int(load_skeleton(layout_id)["joint_count"])
