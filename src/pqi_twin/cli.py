"""Command-line interface for the PQI digital twin MVP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .pipeline import run_pipeline


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pqi-twin",
        description="Audit-defensible Product CMC Digital Twin MVP aligned with HL7 PQI.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run-mvp", help="Run the end-to-end MVP pipeline")
    run_parser.add_argument(
        "--ig-asset",
        required=True,
        type=Path,
        help="Path to PQI package.tgz or full-ig.zip",
    )
    run_parser.add_argument(
        "--input-dir",
        required=True,
        type=Path,
        help="Directory containing CSV/JSON/XML extracts",
    )
    run_parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory to write generated artifacts",
    )
    run_parser.add_argument(
        "--governance-dir",
        required=True,
        type=Path,
        help="Versioned governance store directory",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run-mvp":
        result = run_pipeline(
            ig_asset_path=args.ig_asset,
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            governance_dir=args.governance_dir,
        )
        _print_json(result)
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
