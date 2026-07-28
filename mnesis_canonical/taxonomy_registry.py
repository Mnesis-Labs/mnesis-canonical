"""Taxonomy Registry loader API — the closed vocabularies that travel between repos.

A taxonomy is the **single source of a value domain**: the annotation verbs behind
``annotations/spans.jsonl``'s ``action`` (``manipulation_v1``) and the object
classes behind an :mod:`~mnesis_canonical.semantic` ``ObservationLabel``'s
``class_id`` (``object_class_v1``, C12).

Same shape as :mod:`mnesis_canonical.skeleton_registry` and
:mod:`mnesis_canonical.embodiment_registry` — deliberately, so the standard has
one mechanism for "this value domain is declared elsewhere" instead of three.

Why a registry rather than each consumer's own enum: C12 fuses labels produced by
two different repos (Daedalus on the robot, Eidolon on the headset). If either end
may invent a term, ``cup`` from one end and ``mug`` from the other stop being the
same thing and the fuser needs a mapping table on day one. Adding a term is a PR
against ``taxonomies/<id>.json``, not a local extension.

Reads from the bundled package data (``mnesis_canonical/taxonomies/``), so it
works from source and from a pip-installed wheel alike.
"""
from __future__ import annotations

import importlib.resources as _resources
import importlib.resources.abc as _resources_abc
import json
from pathlib import Path

_PACKAGE = "mnesis_canonical.taxonomies"
_SCHEMA_FILE = "taxonomy.schema.json"

# The key holding the term list tells you what kind of taxonomy the entry is.
# One key per kind (rather than a `kind` field) keeps a single source of truth:
# an entry cannot claim to be an action taxonomy while carrying classes.
_TERM_KEYS = ("actions", "classes")


def _read_traversable(ref: _resources_abc.Traversable) -> dict:
    """Read a JSON file from a Traversable (works for both file-system and zip/egg)."""
    return json.loads(ref.read_text(encoding="utf-8"))


def _taxonomy_paths() -> list[_resources_abc.Traversable]:
    """Return sorted Traversables for the taxonomy JSON files."""
    try:
        ref = _resources.files(_PACKAGE)
    except (TypeError, AttributeError, ModuleNotFoundError):
        ref = Path(__file__).resolve().parent / "taxonomies"
    return sorted(
        (
            p for p in ref.iterdir()
            if p.name.endswith(".json") and p.name != _SCHEMA_FILE
        ),
        key=lambda t: t.name,
    )


def list_taxonomies() -> list[dict]:
    """Return all registered taxonomy entries as a list of dicts."""
    return [_read_traversable(p) for p in _taxonomy_paths()]


def list_taxonomy_ids() -> list[str]:
    """Return the sorted list of registered taxonomy ids."""
    return sorted(e["taxonomy_id"] for e in list_taxonomies())


def load_taxonomy(taxonomy_id: str) -> dict:
    """Load a single taxonomy entry by its ``taxonomy_id`` field.

    Raises:
        LookupError: If no taxonomy with the given id is registered.
    """
    for p in _taxonomy_paths():
        data = _read_traversable(p)
        if data.get("taxonomy_id") == taxonomy_id:
            return data
    raise LookupError(f"Taxonomy '{taxonomy_id}' not found in registry")


def list_terms(taxonomy_id: str) -> list[dict]:
    """Return the term entries of a taxonomy, whichever key they live under."""
    entry = load_taxonomy(taxonomy_id)
    for key in _TERM_KEYS:
        if key in entry:
            return list(entry[key])
    return []


def list_term_ids(taxonomy_id: str) -> tuple[str, ...]:
    """Return the term ids of a taxonomy in file order — the value domain itself.

    These are the values that travel on the wire (``span.action``,
    ``ObservationLabel.class_id``).

    Raises:
        LookupError: If the taxonomy id is not registered.
    """
    return tuple(t["id"] for t in list_terms(taxonomy_id))
