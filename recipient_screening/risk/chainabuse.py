"""Chainabuse provider — free public abuse reports (hacks, scams, phishing,
sanctions exposure). Requires a free API key/secret from chainabuse.com.

API: GET https://api.chainabuse.com/v0/reports?address=<addr> (HTTP Basic).
"""

from __future__ import annotations

import base64
import json
import urllib.parse
import urllib.request

from ..models import CheckResult, Hit, HitKind, Provenance, ScreeningRequest
from ..provenance import utcnow_iso
import hashlib

API_URL = "https://api.chainabuse.com/v0/reports"


class ChainabuseProvider:
    check_id = "chainabuse"

    def __init__(self, api_key: str, api_secret: str, timeout: int = 30):
        self._auth = base64.b64encode(
            f"{api_key}:{api_secret}".encode()).decode()
        self._timeout = timeout

    def assess(self, request: ScreeningRequest,
               sanctioned_addresses: set[str]) -> CheckResult:
        url = API_URL + "?" + urllib.parse.urlencode(
            {"address": request.address})
        req = urllib.request.Request(url, headers={
            "Authorization": f"Basic {self._auth}",
            "Accept": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                payload = resp.read()
            reports = json.loads(payload)
        except Exception as exc:  # network/auth/parse — inconclusive
            return CheckResult(
                check_id=self.check_id, ran=True, ok=False,
                inconclusive_reason=f"Chainabuse query failed: {exc}")
        prov = Provenance(
            source_id=self.check_id, url=url, fetched_at=utcnow_iso(),
            sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload),
            detail=f"{len(reports)} report(s) returned")
        hits = []
        for r in reports:
            category = r.get("category", "unknown")
            hits.append(Hit(
                kind=HitKind.RISK_FLAG,
                source_id=self.check_id,
                matched_value=request.address,
                entry_name=f"Chainabuse report: {category}",
                entry_reference=str(r.get("id", "")),
                detail=(f"Category {category}; subcategory "
                        f"{r.get('subcategory', 'n/a')}; description: "
                        f"{(r.get('description') or '')[:300]}"),
                verbatim={k: r.get(k) for k in
                          ("id", "category", "subcategory", "createdAt",
                           "trusted")},
            ))
        return CheckResult(check_id=self.check_id, ran=True, ok=True,
                           hits=hits, provenance=prov,
                           notes=f"{len(reports)} abuse report(s).")
