"""Data models for the recipient-screening engine.

Everything here is plain dataclasses — no LLM involvement. The verdict is
computed from these records by verdict.py and rendered by report.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class VerdictStatus(str, Enum):
    CLEAR = "CLEAR"
    STOP_HIT = "STOP_HIT"
    STOP_INCONCLUSIVE = "STOP_INCONCLUSIVE"


class HitKind(str, Enum):
    ADDRESS_EXACT = "address_exact"      # exact crypto-address match on a list
    NAME_STRONG = "name_strong"          # name similarity >= hit threshold
    NAME_POSSIBLE = "name_possible"      # name similarity in review band
    RISK_FLAG = "risk_flag"              # confirmed on-chain risk signal
    RISK_PROXIMITY = "risk_proximity"    # indirect exposure signal


@dataclass
class Provenance:
    """Evidence trail for one external source used in a screen."""

    source_id: str
    url: str
    fetched_at: str          # ISO-8601 UTC
    sha256: str
    bytes: int
    detail: str = ""         # e.g. list publish date parsed from the file
    cache_path: str = ""


@dataclass
class Hit:
    """A single match or risk signal."""

    kind: HitKind
    source_id: str
    matched_value: str       # the address or name as it appears on the list
    entry_name: str          # list entry primary name
    entry_reference: str     # list-native identifier (uid / reference number)
    detail: str = ""
    verbatim: dict = field(default_factory=dict)  # raw fields from the source


@dataclass
class CheckResult:
    """Outcome of one check (one list screen or one risk provider)."""

    check_id: str
    ran: bool
    ok: bool                 # True if the check completed conclusively
    inconclusive_reason: str = ""
    hits: list[Hit] = field(default_factory=list)
    provenance: Provenance | None = None
    notes: str = ""


@dataclass
class ScreeningRequest:
    address: str
    chain: str = "ethereum"
    entity_name: str | None = None
    context: str = ""        # free text, e.g. signing-request reference


@dataclass
class Verdict:
    status: VerdictStatus
    reasons: list[str]
    escalate_to: str
    required_action: str


@dataclass
class Report:
    request: ScreeningRequest
    screened_at: str
    checks: list[CheckResult]
    verdict: Verdict
