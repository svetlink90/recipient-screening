"""Command-line interface — the front door every model adapter uses.

Usage:
  python3 -m recipient_screening [--config config.toml] update
  python3 -m recipient_screening [--config config.toml] check-lists
  python3 -m recipient_screening [--config config.toml] screen 0xADDRESS \
      [--entity "Name"] [--chain ethereum] [--context "..."]

Exit codes for `screen`: 0 CLEAR, 2 STOP_HIT, 3 STOP_INCONCLUSIVE, 1 error.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .engine import Engine
from .models import ScreeningRequest, VerdictStatus
from .report import write_reports

EXIT_CODES = {VerdictStatus.CLEAR: 0, VerdictStatus.STOP_HIT: 2,
              VerdictStatus.STOP_INCONCLUSIVE: 3}


def _engine(args) -> Engine:
    return Engine(args.config)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="recipient_screening")
    parser.add_argument("--config", default="config.toml",
                        help="path to config.toml")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("update", help="refresh all sanctions lists")
    sub.add_parser("check-lists", help="show cache freshness/provenance")

    p_ingest = sub.add_parser(
        "ingest", help="ingest a manually downloaded list file "
        "(for sources that block scripts, e.g. EU FSD)")
    p_ingest.add_argument("list_id", help="list id from config.toml")
    p_ingest.add_argument("path", help="downloaded file to ingest")
    p_ingest.add_argument("--note", default="", help="origin note")

    p_screen = sub.add_parser("screen", help="screen a recipient")
    p_screen.add_argument("address")
    p_screen.add_argument("--entity", default=None,
                          help="claimed recipient entity name")
    p_screen.add_argument("--chain", default="ethereum")
    p_screen.add_argument("--context", default="",
                          help="signing-request reference / free text")
    p_screen.add_argument("--no-report", action="store_true",
                          help="print verdict only, don't write report files")

    args = parser.parse_args(argv)
    engine = _engine(args)

    if args.command == "update":
        for lid, status, detail in engine.update_lists():
            print(f"{lid:22s} {status:8s} {detail}")
        return 0

    if args.command == "check-lists":
        for lid, status, detail in engine.list_status():
            print(f"{lid:22s} {status:8s} {detail}")
        return 0

    if args.command == "ingest":
        sha, detail = engine.ingest_list(args.list_id, args.path, args.note)
        print(f"{args.list_id}: ingested, sha256 {sha[:16]}…")
        print(f"detail: {detail}")
        return 0

    request = ScreeningRequest(address=args.address, chain=args.chain,
                               entity_name=args.entity, context=args.context)
    report = engine.screen(request)
    v = report.verdict
    print(f"VERDICT: {v.status.value}")
    for r in v.reasons:
        print(f"  - {r}")
    print(f"ACTION: {v.required_action}")
    if not args.no_report:
        md, js = write_reports(report, engine.reports_dir,
                               engine.cfg["agent"]["checklist_ref"])
        print(f"REPORT_MD: {md}")
        print(f"REPORT_JSON: {js}")
    return EXIT_CODES[v.status]


if __name__ == "__main__":
    sys.exit(main())
