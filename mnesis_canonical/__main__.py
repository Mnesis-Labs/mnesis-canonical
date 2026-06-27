"""CLI: validate an episode JSONL against the Canonical Schema.

    python -m mnesis_canonical validate <path/to/data.jsonl> [--strict-vocab]

Exit code 0 = valid, 1 = invalid (usable as a CI gate / by Ambrosia ingest).
"""
from __future__ import annotations

import argparse
import sys

from .io import read_jsonl
from .validate import validate_frames


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mnesis_canonical")
    sub = parser.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="validate an episode JSONL sidecar")
    v.add_argument("path", help="path to data.jsonl")
    v.add_argument("--strict-vocab", action="store_true", help="reject unknown device/modality")
    args = parser.parse_args(argv)

    if args.cmd == "validate":
        frames = read_jsonl(args.path)
        report = validate_frames(frames, strict_vocab=args.strict_vocab)
        print(f"frames={report.total} valid={report.valid} errors={len(report.errors)}")
        for line_no, msg in report.errors[:50]:
            print(f"  line {line_no}: {msg}")
        return 0 if report.ok else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
