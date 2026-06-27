"""Command-line interface for the Mnesis Canonical Schema.

    python -m mnesis_canonical validate <path/to/data.jsonl>

Prints a ``total=.. valid=.. errors=..`` summary and exits non-zero when the
episode is not conformant, so it can gate CI and be reused by Mnesis Ambrosia
ingest. Exit codes: 0 = all frames valid, 1 = validation errors, 2 = I/O error.
"""
from __future__ import annotations

import argparse
import sys

from .io import read_jsonl
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

    report = validate_frames(frames, strict_vocab=args.strict_vocab)
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mnesis-canonical",
        description="Mnesis Canonical Schema — validation tools for episode sidecars.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="Validate an episode JSONL sidecar.")
    v.add_argument("path", help="Path to the episode data.jsonl")
    v.add_argument(
        "--strict-vocab",
        action="store_true",
        help="Reject unknown source.device / source.modality values.",
    )
    v.add_argument(
        "--max-errors",
        type=int,
        default=20,
        help="Max error lines to print (0 = print all).",
    )
    v.set_defaults(func=_cmd_validate)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
