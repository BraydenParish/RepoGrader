"""Command line interface for cq."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

from .config import Config, dump_default_yaml
from .reporting.json_report import write_json_report
from .reporting.markdown_report import write_markdown_report
from .runner import Runner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cq", description="Code Quotient analyzer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Run analysis")
    scan.add_argument("--path", default=".", help="Path to analyze")
    scan.add_argument("--config", default=None, help="Path to cq.yml config")
    scan.add_argument("--format", default="both", choices=["json", "md", "both"], help="Report formats")
    scan.add_argument("--out", default=None, help="Output directory")
    scan.add_argument("--jobs", default=1, type=int, help="Parallel jobs (unused)")

    subparsers.add_parser("print-schema", help="Print JSON schema")
    subparsers.add_parser("example-config", help="Print default configuration")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "print-schema":
        from .reporting.schema import SCHEMA  # type: ignore

        json.dump(SCHEMA, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if args.command == "example-config":
        sys.stdout.write(dump_default_yaml())
        return 0

    if args.command == "scan":
        config_path = Path(args.config) if args.config else None
        config = Config.load(config_path)
        runner = Runner(config)
        root_path = Path(args.path).resolve()
        report, errors = runner.run(root_path)
        out_dir = Path(args.out or config.report.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        formats = {args.format}
        if args.format == "both":
            formats = {"json", "md"}
        if "json" in formats:
            write_json_report(report, out_dir / "report.json")
        if "md" in formats:
            write_markdown_report(report, out_dir / "report.md")
        if errors:
            for err in errors:
                print(err, file=sys.stderr)
            return 2
        return 0
    return 3


if __name__ == "__main__":
    sys.exit(main())

