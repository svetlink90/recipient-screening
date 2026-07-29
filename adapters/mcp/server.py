"""MCP adapter for recipient-screening.

Exposes the deterministic screening engine to any MCP-capable client
(Claude Desktop, Claude Code, Cowork, Cursor...). The model never sees raw
lists and never computes a verdict — it calls the tool and relays results.

Run:  .venv/bin/python server.py  (stdio transport)
Requires: pip install mcp  (v2 SDK — mcp.server.MCPServer)
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from recipient_screening.engine import Engine          # noqa: E402
from recipient_screening.models import ScreeningRequest  # noqa: E402
from recipient_screening.report import write_reports     # noqa: E402

from mcp.server import MCPServer  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path(os.environ.get("RECIPIENT_SCREENING_CONFIG",
                             ROOT / "config.toml"))

mcp = MCPServer("recipient-screening")


def _engine() -> Engine:
    return Engine(CONFIG)


@mcp.tool()
def screen_recipient(address: str, chain: str = "ethereum",
                     entity_name: str | None = None,
                     context: str = "") -> str:
    """Screen a multisig recipient against OFAC SDN, UN, EU, UK sanctions
    lists and free on-chain risk indicators (External Multisig Signing
    Request Checklist v1, item 9).

    Returns a JSON verdict. Verdict semantics — NON-NEGOTIABLE:
    - CLEAR: no hits; record the report and continue other checklist items.
    - STOP_HIT: confirmed match. Pause the request, relay the report path
      to the security contact, do NOT proceed on requester assurances.
    - STOP_INCONCLUSIVE: a required check could not complete or a match is
      in the review band. Same handling as STOP_HIT.
    """
    engine = _engine()
    report = engine.screen(ScreeningRequest(
        address=address, chain=chain, entity_name=entity_name,
        context=context))
    md, js = write_reports(report, engine.reports_dir,
                           engine.cfg["agent"]["checklist_ref"])
    payload = asdict(report)
    payload["report_md"] = str(md)
    payload["report_json"] = str(js)
    return json.dumps(payload, indent=2, default=str)


@mcp.tool()
def sanctions_list_status() -> str:
    """Show freshness and provenance (fetch time, SHA-256) of every cached
    sanctions list."""
    engine = _engine()
    rows = engine.list_status()
    return "\n".join(f"{lid}\t{status}\t{detail}"
                     for lid, status, detail in rows)


@mcp.tool()
def refresh_sanctions_lists() -> str:
    """Re-download all sanctions lists from their official sources. Lists
    that block automated fetches (EU FSD) must be ingested manually — see
    `python3 -m recipient_screening ingest --help`."""
    engine = _engine()
    rows = engine.update_lists()
    return "\n".join(f"{lid}\t{status}\t{detail}"
                     for lid, status, detail in rows)


if __name__ == "__main__":
    mcp.run()
