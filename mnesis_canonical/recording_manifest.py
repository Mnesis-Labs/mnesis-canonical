"""C2b recording manifest — schema loader and validator.

The recording manifest is the inventory a capture surface (Iris phone, Eidolon
headset, robot recorder) writes next to one recording and uploads as the
``manifest`` part of the C2 episode upload: effective capture options,
per-stream confirmations, the tracker runtime that really ran, every media file
pinned by sha256, and a single timebase. See ``CONTRACTS.md`` (C2b) and
``mnesis_canonical/contracts/c2_recording_manifest.schema.json``.

``validate_recording_manifest(obj) -> list[str]`` returns every problem it finds
(empty list = valid), not just the first. Structure/types come from the bundled
JSON Schema via the optional ``jsonschema`` backend (same dependency as
:func:`mnesis_canonical.validate.validate_frame_jsonschema`); a handful of
cross-field rules that JSON Schema cannot express run in plain Python on top.

Each error is prefixed with the JSON path of the offending field, e.g.
``media[0].sha256: 'abc' does not match '^[0-9a-f]{64}$'``, so a consumer can
tell which field failed without parsing the message.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA_VERSION = "c2/1.0"

_SCHEMA_PATH = (
    Path(__file__).resolve().parent / "contracts" / "c2_recording_manifest.schema.json"
)

_RFC3339_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(\.\d+)?([Zz]|([+-])(\d{2}):(\d{2}))$"
)


def load_recording_manifest_schema() -> dict:
    """Load the bundled C2b recording-manifest JSON Schema (Draft 2020-12).

    Other languages vendor the same file verbatim and pin it by sha256.
    """
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _json_path(parts: object) -> str:
    out = ""
    for part in parts:  # type: ignore[union-attr]
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += f".{part}" if out else str(part)
    return out or "<root>"


def _rfc3339_calendar_error(value: str) -> str | None:
    """Return why an RFC 3339-shaped string is not a real instant, or None."""
    m = _RFC3339_RE.match(value)
    if m is None:
        return None  # shape errors are reported by the schema pattern
    year, month, day, hour, minute, second = (int(g) for g in m.groups()[:6])
    try:
        tz = timezone.utc
        if m.group(9):
            off_h, off_m = int(m.group(10)), int(m.group(11))
            if off_h > 23 or off_m > 59:
                return f"offset {m.group(8)} out of range"
            sign = 1 if m.group(9) == "+" else -1
            tz = timezone(sign * timedelta(hours=off_h, minutes=off_m))
        # RFC 3339 allows second == 60 (leap second); datetime does not.
        datetime(year, month, day, hour, minute, min(second, 59), tzinfo=tz)
        if second > 60:
            raise ValueError("second must be in 0..60")
    except ValueError as e:
        return str(e)
    return None


def _schema_errors(obj: object) -> list[str]:
    try:
        import jsonschema
    except ImportError as e:  # pragma: no cover - exercised only without extra
        raise RuntimeError(
            "validate_recording_manifest requires the optional 'jsonschema' "
            "dependency; install with: pip install mnesis-canonical[jsonschema]"
        ) from e
    validator = jsonschema.Draft202012Validator(load_recording_manifest_schema())
    errors = sorted(
        validator.iter_errors(obj),
        key=lambda e: ([str(p) for p in e.absolute_path], e.message),
    )
    return [f"{_json_path(e.absolute_path)}: {e.message}" for e in errors]


def _semantic_errors(obj: dict) -> list[str]:
    """Cross-field rules JSON Schema cannot express. Tolerates malformed input:
    anything with the wrong shape was already reported by the schema pass."""
    errors: list[str] = []

    timebase = obj.get("timebase")
    if isinstance(timebase, dict) and isinstance(timebase.get("utc_start"), str):
        why = _rfc3339_calendar_error(timebase["utc_start"])
        if why is not None:
            errors.append(
                f"timebase.utc_start: {timebase['utc_start']!r} is not a valid "
                f"RFC 3339 date-time ({why})"
            )

    options = obj.get("resolved_capture_options")
    declared = options.get("streams") if isinstance(options, dict) else None
    declared_names = (
        {s for s in declared if isinstance(s, str)} if isinstance(declared, list) else None
    )

    confirmations = obj.get("stream_confirmations")
    if isinstance(confirmations, list):
        seen: set[str] = set()
        for i, conf in enumerate(confirmations):
            if not isinstance(conf, dict):
                continue
            name = conf.get("name")
            if isinstance(name, str):
                if name in seen:
                    errors.append(
                        f"stream_confirmations[{i}].name: duplicate stream name {name!r}"
                    )
                seen.add(name)
                if declared_names is not None and name not in declared_names:
                    errors.append(
                        f"stream_confirmations[{i}].name: {name!r} is not listed in "
                        "resolved_capture_options.streams"
                    )
            fps = conf.get("fps")
            if conf.get("enabled") is True and isinstance(fps, (int, float)) and fps == 0:
                errors.append(
                    f"stream_confirmations[{i}].fps: enabled stream must have fps > 0"
                )
        if declared_names is not None:
            for name in sorted(declared_names - seen):
                errors.append(
                    f"resolved_capture_options.streams: stream {name!r} has no entry "
                    "in stream_confirmations"
                )

    media = obj.get("media")
    if isinstance(media, list):
        paths: set[str] = set()
        for i, item in enumerate(media):
            if isinstance(item, dict) and isinstance(item.get("path"), str):
                if item["path"] in paths:
                    errors.append(f"media[{i}].path: duplicate media path {item['path']!r}")
                paths.add(item["path"])

    return errors


def validate_recording_manifest(obj: dict) -> list[str]:
    """Validate one C2b recording manifest.

    Returns ALL errors found (empty list = valid). Each error starts with the
    JSON path of the offending field (``<root>`` for top-level problems such
    as a missing or unknown key). Raises RuntimeError if the optional
    ``jsonschema`` dependency is not installed.
    """
    errors = _schema_errors(obj)
    if isinstance(obj, dict):
        errors.extend(_semantic_errors(obj))
    return errors


def load_recording_manifest(path: str | Path) -> dict:
    """Read a recording manifest JSON file and return it as a dict.

    Does not validate; call :func:`validate_recording_manifest` on the result.
    Raises ``ValueError`` if the file is not a JSON object.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: recording manifest must be a JSON object")
    return data
