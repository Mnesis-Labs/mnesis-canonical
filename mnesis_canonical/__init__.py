"""Mnesis Canonical Schema — open standard for embodied spatial-action data.

The reference Python implementation of the Canonical Schema: typed frame,
validation, and JSONL I/O. Apache-2.0. See SPEC.md for the authoritative spec.
"""
from .io import read_jsonl, write_jsonl
from .schema import (
    DEVICES,
    MODALITIES,
    REQUIRED_KEYS,
    VECTOR_LENGTHS,
    CanonicalFrame,
)
from .validate import (
    ValidationReport,
    load_json_schema,
    validate_frame,
    validate_frame_jsonschema,
    validate_frames,
)

__version__ = "0.1.0"

__all__ = [
    "CanonicalFrame",
    "REQUIRED_KEYS",
    "VECTOR_LENGTHS",
    "DEVICES",
    "MODALITIES",
    "validate_frame",
    "validate_frames",
    "validate_frame_jsonschema",
    "load_json_schema",
    "ValidationReport",
    "read_jsonl",
    "write_jsonl",
    "__version__",
]
