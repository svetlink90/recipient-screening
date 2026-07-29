"""Deterministic verdict computation.

Item 9 rule: 'A positive hit or an inconclusive screen is a stop condition:
the request pauses and escalates to the designated security contact rather
than proceeding on the requester's assurances.'

CLEAR            — every required check ran conclusively, no hits.
STOP_HIT         — confirmed match (exact address, strong name, risk flag).
STOP_INCONCLUSIVE— a required check failed/was unavailable, or a match sits
                   in the review band. Both STOP states pause and escalate.
"""

from __future__ import annotations

from .models import (CheckResult, HitKind, Verdict, VerdictStatus)

STOP_ACTION = (
    "PAUSE the signing request. Escalate the attached report to {contact}. "
    "Do not proceed on the requester's assurances. The address and request "
    "stay on hold until the security contact clears or rejects them in "
    "writing (checklist v1 items 9 and 16-17).")

CLEAR_ACTION = (
    "No sanctions or on-chain risk hits found. Record this report with the "
    "request (item 18) and continue the remaining checklist items — this "
    "screen does not satisfy any other item.")


def compute_verdict(checks: list[CheckResult], security_contact: str,
                    required_check_ids: set[str]) -> Verdict:
    reasons: list[str] = []
    hard_hits = 0
    review_signals = 0
    inconclusive: list[str] = []

    for c in checks:
        for h in c.hits:
            if h.kind in (HitKind.ADDRESS_EXACT, HitKind.NAME_STRONG,
                          HitKind.RISK_FLAG):
                hard_hits += 1
                reasons.append(
                    f"{h.kind.value}: {h.matched_value} matched "
                    f"'{h.entry_name}' on {h.source_id}")
            else:
                review_signals += 1
                reasons.append(
                    f"{h.kind.value} (review band): {h.matched_value} vs "
                    f"'{h.entry_name}' on {h.source_id}")
        if not c.ok and c.check_id in required_check_ids:
            inconclusive.append(
                f"{c.check_id}: {c.inconclusive_reason or 'did not complete'}")

    escalate = security_contact
    if inconclusive:
        reasons.append("Inconclusive required checks: "
                       + "; ".join(inconclusive))
    if hard_hits:
        reasons.insert(0, f"{hard_hits} confirmed hit(s).")
        return Verdict(VerdictStatus.STOP_HIT, reasons, escalate,
                       STOP_ACTION.format(contact=escalate))
    if review_signals or inconclusive:
        return Verdict(VerdictStatus.STOP_INCONCLUSIVE, reasons, escalate,
                       STOP_ACTION.format(contact=escalate))
    return Verdict(VerdictStatus.CLEAR,
                   ["All required checks ran; no hits."],
                   escalate, CLEAR_ACTION)
