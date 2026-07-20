"""Embodiment Registry loader API — consumer-facing interface for pip-installed
access to embodiment registry data.

Provides :func:`list_embodiments` and :func:`load_embodiment` that read from
the bundled package data (``mnesis_canonical/embodiments/``), so they work
regardless of whether the package is installed from source or via pip.
"""
from __future__ import annotations

import importlib.resources as _resources
import json
from pathlib import Path

_PACKAGE = "mnesis_canonical.embodiments"
_SCHEMA_FILE = "embodiment.schema.json"


def _embodiment_paths() -> list[Path]:
    """Return sorted list of paths to embodiment JSON files in the package data."""
    try:
        # Python 3.9+ importlib.resources.files returns a Traversable
        ref = _resources.files(_PACKAGE)
    except (TypeError, AttributeError, ModuleNotFoundError):
        # Fallback for older Python or edge cases: use the file system
        ref = Path(__file__).resolve().parent / "embodiments"
    return sorted(
        p
        for p in ref.iterdir()
        if p.suffix == ".json" and p.name != _SCHEMA_FILE
    )


def _read_json(path: Path) -> dict:
    """Read a JSON file from a path (string or Traversable)."""
    return json.loads(path.read_text(encoding="utf-8"))


def _load_schema() -> dict:
    """Load the bundled embodiment JSON Schema."""
    try:
        ref = _resources.files(_PACKAGE) / _SCHEMA_FILE
        return _read_json(ref)
    except (TypeError, AttributeError, ModuleNotFoundError):
        ref = Path(__file__).resolve().parent / "embodiments" / _SCHEMA_FILE
        return _read_json(ref)


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
    return [_read_json(p) for p in _embodiment_paths()]


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
        data = _read_json(p)
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