"""Command-line interface for the Mnesis Canonical Importer framework.

    python -m mnesis_canonical.importers list
    python -m mnesis_canonical.importers describe <path>
    python -m mnesis_canonical.importers import <path> --format <fmt>

Exit codes: 0 = success, 1 = runtime error, 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ._common import ImporterRegistry


def _cmd_list(args: argparse.Namespace) -> int:
    """List all registered importers with their metadata."""
    registry = ImporterRegistry()
    metas = registry.list_formats()
    if not metas:
        print("No importers registered.", file=sys.stderr)
        return 0
    for m in metas:
        exts = ", ".join(m.file_extensions) if m.file_extensions else "(any)"
        print(f"  {m.format_name:<16}  {m.display_name:<30}  [{exts}]")
        if args.verbose:
            print(f"    {'':<16}  {m.description}")
    return 0


def _cmd_describe(args: argparse.Namespace) -> int:
    """Describe a source file by probing all registered importers by extension."""
    path = Path(args.path)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2

    registry = ImporterRegistry()
    importer = _resolve_by_extension(registry, path, args.format)
    if importer is None:
        print(f"error: no importer handles {path.suffix}", file=sys.stderr)
        return 1

    try:
        info = importer().describe_source(path)
    except NotImplementedError:
        print(f"error: describe not implemented for {args.format}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(json.dumps(info, indent=2, default=str))
    return 0


def _cmd_import(args: argparse.Namespace) -> int:
    """Import a source file into canonical frame dicts."""
    path = Path(args.path)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2

    registry = ImporterRegistry()
    importer = _resolve_by_extension(registry, path, args.format)
    if importer is None:
        print(f"error: no importer handles {path.suffix}", file=sys.stderr)
        return 1

    try:
        frames = importer().import_episode(path)
    except NotImplementedError:
        print(f"error: import not implemented for {args.format}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    for frame in frames:
        print(json.dumps(frame, ensure_ascii=False))
    return 0


def _resolve_by_extension(
    registry: ImporterRegistry,
    path: Path,
    format_name: str | None,
) -> type | None:
    """Resolve an importer class by explicit format name or file extension."""
    if format_name:
        try:
            return registry.get(format_name)
        except KeyError:
            print(
                f"error: unknown format '{format_name}'",
                file=sys.stderr,
            )
            return None

    suffix = path.suffix.lower()
    for meta in registry.list_formats():
        if suffix in meta.file_extensions:
            return registry.get(meta.format_name)
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mnesis-canonical-importers",
        description="Mnesis Canonical Importer framework — ingest multi-format "
        "episode data into the Canonical Schema.",
    )
    sub = parser.add_subparsers(dest="command")

    # --- list ---
    ls = sub.add_parser("list", help="List registered importers.")
    ls.add_argument(
        "-v", "--verbose", action="store_true",
        help="Show full description for each importer.",
    )
    ls.set_defaults(func=_cmd_list)

    # --- describe ---
    desc = sub.add_parser(
        "describe",
        help="Print metadata about a source file (duration, topics, …).",
    )
    desc.add_argument("path", help="Path to the source file.")
    desc.add_argument(
        "--format", "-f",
        help="Importer format name (auto-detected from extension by default).",
    )
    desc.set_defaults(func=_cmd_describe)

    # --- import ---
    imp = sub.add_parser(
        "import",
        help="Import a source file and emit canonical JSONL frames to stdout.",
    )
    imp.add_argument("path", help="Path to the source file.")
    imp.add_argument(
        "--format", "-f", required=True,
        help="Importer format name (e.g. mcap, xrobotoolkit).",
    )
    imp.set_defaults(func=_cmd_import)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command is None:
        build_parser().print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())