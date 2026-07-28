"""Command-line interface for the Mnesis Canonical Schema.

    python -m mnesis_canonical validate <path/to/data.jsonl>

Prints a ``total=.. valid=.. errors=..`` summary and exits non-zero when the
episode is not conformant, so it can gate CI and be reused by Mnesis Ambrosia
ingest. Exit codes: 0 = all frames valid, 1 = validation errors, 2 = I/O error.
"""
from __future__ import annotations

import argparse
import json
import sys

from .io import read_jsonl, write_jsonl
from .isaac import to_isaac
from .lerobot import to_lerobot
from .manifest import manifest_for_episode, validate_manifest, write_manifest
from .migrate import HAND_V0_FRAME, HAND_V0_LAYOUT, migrate_hand_v0_frames
from .schema import HAND_FRAMES, get_schema_version
from .validate import validate_frames


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        frames = read_jsonl(args.path)
    except FileNotFoundError:
        print(f"error: file not found: {args.path}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as e:
        print(f"error: could not read {args.path}: {e}", file=sys.stderr)
        return 2

    report = validate_frames(
        frames, strict_vocab=args.strict_vocab, strict_stable=args.strict_stable,
    )
    print(f"total={report.total} valid={report.valid} errors={len(report.errors)}")

    if report.errors:
        limit = args.max_errors or None
        for line_no, msg in report.errors[:limit]:
            print(f"  line {line_no}: {msg}", file=sys.stderr)
        if args.max_errors and len(report.errors) > args.max_errors:
            print(f"  ... and {len(report.errors) - args.max_errors} more", file=sys.stderr)
    elif report.total == 0:
        print("error: episode is empty (no frames)", file=sys.stderr)

    return 0 if report.ok else 1


def _cmd_manifest(args: argparse.Namespace) -> int:
    if args.check:
        result = validate_manifest(args.episode_dir)
        if result["ok"]:
            print("manifest.json is consistent with data.jsonl")
            return 0
        for err in result["errors"]:
            print(f"  {err}", file=sys.stderr)
        return 1

    try:
        if args.no_write:
            manifest = manifest_for_episode(args.episode_dir)
        else:
            manifest = json.loads(write_manifest(args.episode_dir).read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"error: no data.jsonl under: {args.episode_dir}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as e:
        print(f"error: could not build manifest for {args.episode_dir}: {e}", file=sys.stderr)
        return 2
    print(json.dumps(manifest, indent=2))
    return 0


def _cmd_convert(args: argparse.Namespace) -> int:
    try:
        frames = read_jsonl(args.path)
    except FileNotFoundError:
        print(f"error: file not found: {args.path}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as e:
        print(f"error: could not read {args.path}: {e}", file=sys.stderr)
        return 2

    fmt = args.to
    try:
        if fmt == "lerobot":
            columns = to_lerobot(frames)
            with open(args.out, "w", encoding="utf-8", newline="") as f:
                json.dump(columns, f, ensure_ascii=False)
                f.write("\n")
        elif fmt == "isaac":
            write_jsonl(args.out, to_isaac(frames))
        else:
            print(
                f"error: unknown format '{fmt}' (expected lerobot or isaac)",
                file=sys.stderr,
            )
            return 1
    except OSError as e:
        print(f"error: could not write {args.out}: {e}", file=sys.stderr)
        return 2

    return 0


def _cmd_migrate(args: argparse.Namespace) -> int:
    try:
        frames = read_jsonl(args.path)
    except FileNotFoundError:
        print(f"error: file not found: {args.path}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as e:
        print(f"error: could not read {args.path}: {e}", file=sys.stderr)
        return 2

    if args.migration != "hand_v0":
        print(
            f"error: unknown migration '{args.migration}' (expected hand_v0)",
            file=sys.stderr,
        )
        return 1

    try:
        migrated = migrate_hand_v0_frames(
            frames, layout=args.layout, reference_frame=args.frame,
        )
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    changed = sum(
        1 for before, after in zip(frames, migrated, strict=True) if before != after
    )
    try:
        write_jsonl(args.out, migrated)
    except OSError as e:
        print(f"error: could not write {args.out}: {e}", file=sys.stderr)
        return 2

    print(f"migrated={changed} unchanged={len(frames) - changed} out={args.out}")
    report = validate_frames(migrated)
    if not report.ok:
        for line_no, msg in report.errors[:20]:
            print(f"  line {line_no}: {msg}", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mnesis-canonical",
        description="Mnesis Canonical Schema — validation tools for episode sidecars.",
    )
    parser.add_argument(
        "--schema-version",
        action="store_true",
        help="Print the Canonical Schema version and exit.",
    )
    sub = parser.add_subparsers(dest="command")

    v = sub.add_parser("validate", help="Validate an episode JSONL sidecar.")
    v.add_argument("path", help="Path to the episode data.jsonl")
    v.add_argument(
        "--strict-vocab",
        action="store_true",
        help="Reject unknown source.device / source.modality values.",
    )
    v.add_argument(
        "--strict-stable",
        action="store_true",
        help="Reject frames carrying any [experimental] field (freeze-only ingest).",
    )
    v.add_argument(
        "--max-errors",
        type=int,
        default=20,
        help="Max error lines to print (0 = print all).",
    )
    v.set_defaults(func=_cmd_validate)

    m = sub.add_parser(
        "manifest",
        help="Build (and write) an episode's manifest.json from its data.jsonl.",
    )
    m.add_argument("episode_dir", help="Episode directory containing data.jsonl")
    m.add_argument(
        "--no-write",
        action="store_true",
        help="Print the manifest to stdout without writing manifest.json.",
    )
    m.add_argument(
        "--check",
        action="store_true",
        help="Validate existing manifest.json for consistency with sibling data.jsonl.",
    )
    m.set_defaults(func=_cmd_manifest)

    c = sub.add_parser(
        "convert",
        help="Convert a canonical JSONL sidecar to LeRobot (columnar JSON) or Isaac (JSONL).",
    )
    c.add_argument("path", help="Path to the source data.jsonl")
    c.add_argument("--to", required=True,
                   help="Target format (lerobot → columnar JSON; isaac → JSONL)")
    c.add_argument("--out", required=True, help="Output file path")
    c.set_defaults(func=_cmd_convert)

    mig = sub.add_parser(
        "migrate",
        help="Rewrite an episode produced before a field was standardised.",
    )
    mig.add_argument("path", help="Path to the source data.jsonl")
    mig.add_argument(
        "--migration",
        default="hand_v0",
        help=(
            "Which migration to apply. 'hand_v0' rewrites the pre-C11 Iris hand "
            "fields (hand_left_kpts3d / hand_right_kpts3d / hand_kpts_source) to "
            "observation.hand.*, drops the derived hand_pose, and declares the "
            "layout + reference frame."
        ),
    )
    mig.add_argument(
        "--layout",
        default=HAND_V0_LAYOUT,
        help=f"Skeleton layout id to declare (default: {HAND_V0_LAYOUT}).",
    )
    mig.add_argument(
        "--frame",
        default=HAND_V0_FRAME,
        choices=list(HAND_FRAMES),
        help=f"Value for observation.hand.frame (default: {HAND_V0_FRAME}).",
    )
    mig.add_argument("--out", required=True, help="Output data.jsonl path")
    mig.set_defaults(func=_cmd_migrate)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.schema_version:
        print(get_schema_version())
        return 0
    if args.command is None:
        build_parser().print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
