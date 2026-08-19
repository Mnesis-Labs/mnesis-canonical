"""Embodiment Registry loader API — consumer-facing interface for pip-installed
access to embodiment registry data.

Provides :func:`list_embodiments` and :func:`load_embodiment` that read from
the bundled package data (``mnesis_canonical/embodiments/``), so they work
regardless of whether the package is installed from source or via pip.
"""
from __future__ import annotations

import importlib.resources as _resources
import importlib.resources.abc as _resources_abc
import json
from pathlib import Path

_PACKAGE = "mnesis_canonical.embodiments"
_SCHEMA_FILE = "embodiment.schema.json"


def _read_traversable(ref: _resources_abc.Traversable) -> dict:
    """Read a JSON file from a Traversable (works for both file-system and zip/egg)."""
    return json.loads(ref.read_text(encoding="utf-8"))


def _embodiment_paths() -> list[_resources_abc.Traversable]:
    """Return sorted list of Traversables for embodiment JSON files.

    Uses ``importlib.resources`` native API (``Traversable.iterdir``, ``.name``)
    rather than ``Path``, so the code works correctly even when the package is
    distributed as a zip/egg (where ``Traversable`` is **not** a ``Path``).
    """
    try:
        ref = _resources.files(_PACKAGE)
    except (TypeError, AttributeError, ModuleNotFoundError):
        ref = Path(__file__).resolve().parent / "embodiments"
    return sorted(
        (p for p in ref.iterdir() if p.name.endswith(".json") and p.name != _SCHEMA_FILE),
        key=lambda t: t.name,
    )


def _load_schema() -> dict:
    """Load the bundled embodiment JSON Schema."""
    try:
        ref = _resources.files(_PACKAGE) / _SCHEMA_FILE
        return _read_traversable(ref)
    except (TypeError, AttributeError, ModuleNotFoundError):
        ref = Path(__file__).resolve().parent / "embodiments" / _SCHEMA_FILE
        return json.loads(ref.read_text(encoding="utf-8"))


def _validate_via_schema(embodiment: dict, schema: dict) -> list[str]:
    """Validate an embodiment dict against the JSON Schema.

    Returns a list of human-readable errors (empty = valid).  Returns an error
    message if ``jsonschema`` is not installed (the check is best-effort when the
    optional extra is missing).
    """
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema not installed — schema validation skipped"]
    validator = jsonschema.Draft202012Validator(schema)
    return [err.message for err in sorted(validator.iter_errors(embodiment), key=str)]


def list_embodiments() -> list[dict]:
    """Return all embodiment registry entries as a list of dicts.

    Reads from the bundled package data, so it works both from source and from
    a pip-installed wheel.

    Returns:
        A list of embodiment dicts, one per ``.json`` file in the package data
        (excluding the schema file itself).  Each dict is the full JSON object
        from the file.
    """
    return [_read_traversable(p) for p in _embodiment_paths()]


def load_embodiment(embodiment_id: str, *, validate: bool = False) -> dict:
    """Load a single embodiment registry entry by its ``id`` field.

    Args:
        embodiment_id: The ``id`` value of the embodiment (e.g. ``"airbot_play"``).
        validate: If ``True``, validate the embodiment against the bundled JSON
            Schema (requires the optional ``jsonschema`` dependency).  Default
            ``False``.

    Returns:
        The embodiment dict.

    Raises:
        LookupError: If no embodiment with the given ``id`` is found.
        RuntimeError: If ``validate=True`` and ``jsonschema`` is not installed
            or the embodiment fails schema validation.
    """
    for p in _embodiment_paths():
        data = _read_traversable(p)
        if data.get("id") == embodiment_id:
            if validate:
                schema = _load_schema()
                errs = _validate_via_schema(data, schema)
                if errs:
                    raise RuntimeError(
                        f"Embodiment '{embodiment_id}' failed schema validation: {errs}"
                    )
            return data
    raise LookupError(f"Embodiment '{embodiment_id}' not found in registry")


def list_embodiment_ids() -> list[str]:
    """Return the sorted list of registered embodiment IDs."""
    return sorted(data["id"] for data in list_embodiments())


def list_camera_names(embodiment_id: str) -> list[str]:
    """Return the camera names declared by an embodiment's ``capture.cameras[]``.

    This is the authoritative value domain for ``observation.images.<camera_name>``
    keys under the ``ego_multicam_v1`` profile (SPEC §Profiles): a name that is not
    in this list is a typo, not a new camera.  Names are unique **within** the
    embodiment only — see SPEC for the cross-embodiment rule.

    Returns an empty list when the embodiment declares no cameras (older registry
    entries have no ``capture`` section at all).

    Raises:
        LookupError: If no embodiment with the given ``id`` is found.
    """
    cameras = load_embodiment(embodiment_id).get("capture", {}).get("cameras", [])
    return [c["name"] for c in cameras if "name" in c]


def reference_camera(embodiment_id: str) -> str | None:
    """Return the embodiment's reference camera name, or ``None`` if undeclared.

    The reference camera is the one whose frame rate defines the ``data.jsonl`` row
    cadence when a rig mixes frame rates (e.g. 60 fps wide + 30 fps fisheye); the
    other cameras declare their own ``fps`` in ``capture.cameras[]`` and contribute
    only a path per row.  See SPEC §Profiles → ``ego_multicam_v1``.

    Raises:
        LookupError: If no embodiment with the given ``id`` is found.
    """
    return load_embodiment(embodiment_id).get("capture", {}).get("reference_camera")