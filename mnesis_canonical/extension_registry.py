"""Extension registry loader — the public list of fields that are *not* standard yet.

A capture surface that needs a field the standard does not have writes it as
``x-<vendor>.<field>`` (see :data:`mnesis_canonical.schema.EXTENSION_PREFIX`) and
adds one entry to ``extensions/registry.json``.  That PR touches this repo only:
no cross-repo contract card, no waiting on a canonical release.  The point is
economic, not bureaucratic — as long as declaring an extension costs more than
quietly shipping one, producers ship quietly and canonical is the last to know
(issue #69; the Iris hand fields in Parthenon#47 are the worked example).

What canonical gets back is an early-warning list of **what is about to become
standard**, instead of a full-fleet audit two weeks later.

Same loader shape as :mod:`mnesis_canonical.skeleton_registry` /
:mod:`mnesis_canonical.embodiment_registry`, and reads from bundled package data
so it works from source and from a pip-installed wheel alike.
"""
from __future__ import annotations

import importlib.resources as _resources
import importlib.resources.abc as _resources_abc
import json
from functools import lru_cache as _lru_cache
from pathlib import Path

_PACKAGE = "mnesis_canonical.extensions"
_REGISTRY_FILE = "registry.json"
_SCHEMA_FILE = "registry.schema.json"

# Values of an entry's ``promotion_status`` — see extensions/registry.schema.json.
PROMOTION_STATUSES = ("active", "proposed", "promoted", "withdrawn")


def _read(name: str) -> dict:
    """Read a bundled JSON file by name (package data, with a source fallback)."""
    try:
        ref: _resources_abc.Traversable = _resources.files(_PACKAGE) / name
        return json.loads(ref.read_text(encoding="utf-8"))
    except (TypeError, AttributeError, ModuleNotFoundError):
        path = Path(__file__).resolve().parent / "extensions" / name
        return json.loads(path.read_text(encoding="utf-8"))


def load_registry() -> dict:
    """Return the whole registry document (``{"version": .., "extensions": [..]}``)."""
    return _read(_REGISTRY_FILE)


def load_registry_schema() -> dict:
    """Return the bundled JSON Schema for ``extensions/registry.json``."""
    return _read(_SCHEMA_FILE)


def list_extensions(*, promotion_status: str | None = None) -> list[dict]:
    """Return the registered extension entries, sorted by ``name``.

    Args:
        promotion_status: Optional filter, e.g. ``"proposed"`` to see what
            producers are asking to have standardised next.
    """
    entries = list(load_registry().get("extensions", []))
    if promotion_status is not None:
        entries = [e for e in entries if e.get("promotion_status") == promotion_status]
    return sorted(entries, key=lambda e: e.get("name", ""))


def list_extension_names(*, promotion_status: str | None = None) -> list[str]:
    """Return the sorted names of registered extension keys."""
    return [e["name"] for e in list_extensions(promotion_status=promotion_status)]


@_lru_cache(maxsize=1)
def _index() -> dict[str, dict]:
    """name -> entry, read once.

    Cached because :func:`find_extension` is called per unknown key per frame by
    the validator's warning pass; an episode is millions of keys.
    """
    return {e["name"]: e for e in load_registry().get("extensions", []) if "name" in e}


def load_extension(name: str) -> dict:
    """Return a single registry entry by its ``name`` (the on-the-wire key).

    Raises:
        LookupError: If the key is not registered.
    """
    entry = _index().get(name)
    if entry is None:
        raise LookupError(f"Extension '{name}' not found in extensions/registry.json")
    return dict(entry)


def find_extension(name: str) -> dict | None:
    """Return the registry entry for ``name``, or ``None`` when unregistered."""
    entry = _index().get(name)
    return dict(entry) if entry is not None else None
