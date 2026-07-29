"""Etherscan inbound-proximity provider (free API tier).

Scans the recipient's recent inbound transactions and flags any sender that
is (a) on a sanctions list (addresses extracted by the list screen) or
(b) in the offline known-mixer set. This is the 'mixer proximity / high-risk
exposure' leg of item 9 built entirely on free sources.

Ethereum mainnet only in v0.1. Requires a free etherscan.io API key.
Uses the Etherscan V2 API (V1 was deprecated by Etherscan).
"""

from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request

from ..matching import normalize_address
from ..models import CheckResult, Hit, HitKind, Provenance, ScreeningRequest
from ..provenance import utcnow_iso
from .known_sets import KNOWN_BAD

API_URL = "https://api.etherscan.io/v2/api"
CHAIN_ID = "1"  # ethereum mainnet


class EtherscanProximityProvider:
    check_id = "etherscan_proximity"

    def __init__(self, api_key: str, lookback_txs: int = 200, timeout: int = 30):
        self._key = api_key
        self._lookback = lookback_txs
        self._timeout = timeout

    def assess(self, request: ScreeningRequest,
               sanctioned_addresses: set[str]) -> CheckResult:
        if request.chain not in ("ethereum", "mainnet", "eth"):
            return CheckResult(
                check_id=self.check_id, ran=False, ok=True,
                notes=f"Skipped — proximity scan supports ethereum only, "
                      f"got chain '{request.chain}'.")
        target = normalize_address(request.address)
        params = {
            "chainid": CHAIN_ID,
            "module": "account", "action": "txlist", "address": target,
            "startblock": 0, "endblock": 99999999, "page": 1,
            "offset": self._lookback, "sort": "desc", "apikey": self._key,
        }
        url = API_URL + "?" + urllib.parse.urlencode(params)
        try:
            with urllib.request.urlopen(url, timeout=self._timeout) as resp:
                payload = resp.read()
            data = json.loads(payload)
        except Exception as exc:
            return CheckResult(
                check_id=self.check_id, ran=True, ok=False,
                inconclusive_reason=f"Etherscan query failed: {exc}")
        if str(data.get("status")) not in ("1", "0"):
            return CheckResult(
                check_id=self.check_id, ran=True, ok=False,
                inconclusive_reason=f"Etherscan error: {data.get('message')} "
                                    f"{data.get('result')}")
        result = data.get("result")
        # status "0" with result "No transactions found" (a string, not a
        # list) is the normal empty shape for fresh addresses.
        txs = result if isinstance(result, list) else []
        prov = Provenance(
            source_id=self.check_id, url="https://api.etherscan.io/v2/api "
            "(chainid=1, account/txlist)", fetched_at=utcnow_iso(),
            sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload),
            detail=f"{len(txs)} most recent txs scanned")
        flagged = {a.lower() for a in sanctioned_addresses} | set(KNOWN_BAD)
        hits: list[Hit] = []
        seen_senders: set[str] = set()
        for tx in txs:
            if (tx.get("to") or "").lower() != target:
                continue  # inbound only
            sender = (tx.get("from") or "").lower()
            if sender in flagged and sender not in seen_senders:
                seen_senders.add(sender)
                label = KNOWN_BAD.get(sender, "sanctions-listed address")
                hits.append(Hit(
                    kind=HitKind.RISK_PROXIMITY,
                    source_id=self.check_id,
                    matched_value=sender,
                    entry_name=label,
                    entry_reference=tx.get("hash", ""),
                    detail=(f"Recipient received funds directly from {label} "
                            f"in tx {tx.get('hash', '?')} "
                            f"(block {tx.get('blockNumber', '?')})."),
                    verbatim={"from": sender, "to": target,
                              "hash": tx.get("hash"),
                              "blockNumber": tx.get("blockNumber"),
                              "valueWei": tx.get("value")},
                ))
        return CheckResult(
            check_id=self.check_id, ran=True, ok=True, hits=hits,
            provenance=prov,
            notes=f"Scanned {len(txs)} recent txs for inbound exposure to "
                  f"{len(flagged)} flagged addresses.")
