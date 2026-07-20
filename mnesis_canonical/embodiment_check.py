"""Embodiment registry validation — checks all ``embodiments/<id>.json`` files
against the bundled JSON Schema (``embodiment.schema.json``).

Usage::

    python -m mnesis_canonical.embodiment_check          # validate all
    python -m mnesis_canonical.embodiment_check --list    # list entries

Exit codes: 0 = ok, 1 = validation error, 2 = I/O error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_EMBODIMENTS_DIR = Path(__file__).resolve().parent.parent / "embodiments"
_SCHEMA_PATH = _EMBODIMENTS_DIR / "embodiment.schema.json"


def _discover_embodiments() -> list[Path]:
    """Return sorted list of embodiment JSON paths (excluding the schema)."""
    return sorted(
        p for p in _EMBODIMENTS_DIR.iterdir()
        if p.is_file() and p.suffix == ".json" and p.name != "embodiment.schema.json"
    )


def load_schema() -> dict:
    """Load the embodiment JSON Schema as a dict."""
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_embodiment(path: Path) -> dict:
    """Load one embodiment JSON file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_embodiment_jsonschema(embodiment: dict, schema: dict) -> list[str]:
    """Validate one embodiment dict against the JSON Schema.

    Returns a list of human-readable errors (empty = valid). Raises RuntimeError
    if ``jsonschema`` is not installed.
    """
    try:
        import jsonschema
    except ImportError as e:
        raise RuntimeError(
            "validate_embodiment_jsonschema requires the optional 'jsonschema' "
            "dependency; install with: pip install mnesis-canonical[jsonschema]"
        ) from e
    validator = jsonschema.Draft202012Validator(schema)
    return [err.message for err in sorted(validator.iter_errors(embodiment), key=str)]


def validate_embodiment(embodiment: dict) -> list[str]:
    """Return a list of errors for one embodiment dict (empty list = valid).

    Pure-Python checks that complement the JSON Schema (length consistency, etc.).
    """
    errors: list[str] = []

    # joint_limits arrays must match joint_names length
    jn = embodiment.get("joint_names", [])
    jl = embodiment.get("joint_limits", {})
    jmin = jl.get("min", [])
    jmax = jl.get("max", [])
    if len(jmin) != len(jn):
        errors.append(
            f"joint_limits.min has {len(jmin)} entries, expected {len(jn)} "
            f"(matching joint_names)"
        )
    if len(jmax) != len(jn):
        errors.append(
            f"joint_limits.max has {len(jmax)} entries, expected {len(jn)} "
            f"(matching joint_names)"
        )

    # For dual-arm embodiments, joint_names should be even-split
    arms = embodiment.get("arms", 1)
    dof = embodiment.get("dof_per_arm", 0)
    if arms > 1:
        joints_per_arm = len(jn) // arms
        if len(jn) % arms != 0:
            errors.append(
                f"joint_names length ({len(jn)}) not divisible by arms ({arms})"
            )
        elif joints_per_arm < dof:
            errors.append(
                f"joint_names per arm ({joints_per_arm}) < dof_per_arm ({dof}) "
                f"— missing gripper joint?"
            )

    # File name must match id field
    return errors


def cmd_validate() -> int:
    """Validate all embodiment files against the schema."""
    schema = load_schema()
    paths = _discover_embodiments()
    if not paths:
        print("No embodiment files found.", file=sys.stderr)
        return 2

    ok = True
    for path in paths:
        try:
            data = load_embodiment(path)
        except (OSError, json.JSONDecodeError) as e:
            print(f"  {path.name}  ... LOAD ERROR: {e}", file=sys.stderr)
            ok = False
            continue

        errs = validate_embodiment_jsonschema(data, schema)
        errs += validate_embodiment(data)

        if errs:
            print(f"  {path.name}  ... FAIL")
            for e in errs:
                print(f"    - {e}", file=sys.stderr)
            ok = False
        else:
            # Verify id matches filename stem
            stem = path.stem
            if data.get("id") != stem:
                print(
                    f"  {path.name}  ... id mismatch: '{data.get('id')}' != '{stem}'",
                    file=sys.stderr,
                )
                ok = False
            else:
                print(f"  {path.name}  ... OK")

    if ok:
        print(f"\nAll {len(paths)} embodiment(s) pass validation.")
        return 0
    return 1


def cmd_list() -> int:
    """List all embodiment entries."""
    paths = _discover_embodiments()
    for path in paths:
        data = load_embodiment(path)
        eid = data.get("id", "?")
        name = data.get("display_name", "?")
        arms = data.get("arms", "?")
        dof = data.get("dof_per_arm", "?")
        print(f"  {eid:<20}  {name:<25}  {arms} arm(s)  {dof} DoF/arm")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m mnesis_canonical.embodiment_check",
        description="Validate embodiment registry entries against embodiment.schema.json.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List embodiment entries.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list:
        return cmd_list()
    return cmd_validate()


if __name__ == "__main__":
    sys.exit(main())