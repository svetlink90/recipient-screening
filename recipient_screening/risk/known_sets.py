"""Offline known-address sets: mixers and widely published bad actors.

Sources: OFAC SDN designations of Tornado Cash contracts (2022-08-08,
supplemented 2022-11-08), public project documentation. These addresses are
also on the SDN list itself, so the list screen catches them too — this set
exists primarily to seed proximity analysis on chains/providers where only
recent history is scanned.
"""

from __future__ import annotations

from ..matching import normalize_address
from ..models import CheckResult, Hit, HitKind, ScreeningRequest

# Tornado Cash (Ethereum mainnet) — per OFAC SDN designation.
TORNADO_CASH_MAINNET = {
    "0x12d66f87a04a9e220743712ce6d9bb1b5616b8fc": "Tornado Cash 0.1 ETH pool",
    "0x47ce0c6ed5b0ce3d3a51fdb1c52dc66a7c3c2936": "Tornado Cash 1 ETH pool",
    "0x910cbd523d972eb0a6f4cae4618ad62622b39dbf": "Tornado Cash 10 ETH pool",
    "0xa160cdab225685da1d56aa342ad8841c3b53f291": "Tornado Cash 100 ETH pool",
    "0x722122df12d4e14e13ac3b6895a86e84145b6967": "Tornado Cash Proxy/Router",
}

KNOWN_BAD: dict[str, str] = {**TORNADO_CASH_MAINNET}


class KnownSetsProvider:
    check_id = "known_sets"

    def assess(self, request: ScreeningRequest,
               sanctioned_addresses: set[str]) -> CheckResult:
        addr = normalize_address(request.address)
        hits: list[Hit] = []
        if addr in KNOWN_BAD:
            label = KNOWN_BAD[addr]
            hits.append(Hit(
                kind=HitKind.RISK_FLAG,
                source_id=self.check_id,
                matched_value=request.address,
                entry_name=label,
                entry_reference="known_sets:tornado_cash",
                detail=f"Address is a known mixer contract ({label}). "
                       "Source: OFAC SDN designation, public documentation.",
                verbatim={"address": addr, "label": label},
            ))
        return CheckResult(
            check_id=self.check_id, ran=True, ok=True, hits=hits,
            notes="Offline known-mixer set (Tornado Cash pools/router).",
        )
