"""OpenSanctions provider — consolidated screening against their 'sanctions'
dataset (OFAC, UN, EU, UK and other national lists normalised into
FollowTheMoney entities). Supplementary leg: the five publisher-direct
sanctions lists stay authoritative; this catches consolidation gaps and
cross-confirms them with an independent normalisation pipeline.

Two deterministic legs:
- Address: GET /search/{dataset}?q=<address>. Full-text search returns
  candidates; only an exact publicKey match on a CryptoWallet entity counts
  as a hit — fuzzy text matches are ignored.
- Name: POST /match/{dataset} with the claimed entity name. OpenSanctions
  scores (0-1) map onto the same stop bands as the list screen: >= hit
  threshold is a confirmed hit, >= review threshold stops inconclusive for
  human disambiguation.

API: https://api.opensanctions.org — free tier, ApiKey auth.
"""

from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request

from ..matching import normalize_address
from ..models import CheckResult, Hit, HitKind, Provenance, ScreeningRequest
from ..provenance import utcnow_iso

API_URL = "https://api.opensanctions.org"


class OpenSanctionsProvider:
    check_id = "opensanctions"

    def __init__(self, api_key: str, dataset: str = "sanctions",
                 hit_threshold: float = 0.90,
                 review_threshold: float = 0.70, timeout: int = 30):
        self._key = api_key
        self._dataset = dataset
        self._hit = hit_threshold
        self._review = review_threshold
        self._timeout = timeout

    # ---------- HTTP helpers (bytes out for provenance) ----------

    def _request(self, url: str, body: bytes | None = None) -> bytes:
        req = urllib.request.Request(url, data=body, headers={
            "Authorization": f"ApiKey {self._key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            return resp.read()

    # ---------- legs ----------

    def _address_hits(self, target: str, hits: list[Hit]) -> bytes:
        url = (f"{API_URL}/search/{self._dataset}?"
               + urllib.parse.urlencode({"q": target, "limit": 10}))
        payload = self._request(url)
        data = json.loads(payload)
        results = data.get("results") or []
        # The same wallet appears once per member list — merge into one hit.
        matched: dict[str, dict] = {}
        for r in results:
            keys = [(k or "") for k in
                    (r.get("properties", {}).get("publicKey") or [])]
            if r.get("schema") != "CryptoWallet" or \
                    target.lower() not in [k.lower() for k in keys]:
                continue
            m = matched.setdefault(target.lower(), {
                "ids": [], "datasets": [], "key": keys[0] if keys else target})
            m["ids"].append(str(r.get("id", "")))
            m["datasets"] += [d for d in (r.get("datasets") or [])
                              if d not in m["datasets"]]
        for m in matched.values():
            datasets = ", ".join(m["datasets"])
            hits.append(Hit(
                kind=HitKind.ADDRESS_EXACT,
                source_id=self.check_id,
                matched_value=m["key"],
                entry_name=m["key"],
                entry_reference=";".join(m["ids"]),
                detail=(f"Exact wallet match in OpenSanctions "
                        f"'{self._dataset}' dataset (member lists: "
                        f"{datasets})."),
                verbatim={"ids": m["ids"], "schema": "CryptoWallet",
                          "datasets": m["datasets"],
                          "publicKey": [m["key"]]}))
        return payload

    def _name_hits(self, entity_name: str, hits: list[Hit]) -> bytes:
        url = f"{API_URL}/match/{self._dataset}"
        body = json.dumps({"queries": {"q1": {
            "schema": "LegalEntity",
            "properties": {"name": [entity_name]},
            "limit": 10,
        }}}).encode()
        payload = self._request(url, body=body)
        data = json.loads(payload)
        resp = (data.get("responses") or {}).get("q1") or {}
        if resp.get("status") not in (None, 200):
            raise RuntimeError(f"match query status {resp.get('status')}")
        for r in resp.get("results") or []:
            score = float(r.get("score") or 0.0)
            datasets = ", ".join(r.get("datasets") or [])
            if score >= self._hit:
                kind, band = HitKind.NAME_STRONG, f">= {self._hit}"
            elif score >= self._review:
                kind = HitKind.NAME_POSSIBLE
                band = f"{self._review}-{self._hit} (human disambiguation)"
            else:
                continue
            hits.append(Hit(
                kind=kind, source_id=self.check_id,
                matched_value=r.get("caption", entity_name),
                entry_name=r.get("caption", entity_name),
                entry_reference=str(r.get("id", "")),
                detail=(f"OpenSanctions match score {score:.3f} ({band}) "
                        f"vs '{entity_name}' in '{self._dataset}' dataset "
                        f"(member lists: {datasets})."),
                verbatim={"id": r.get("id"), "schema": r.get("schema"),
                          "score": score, "datasets": r.get("datasets"),
                          "caption": r.get("caption")}))
        return payload

    # ---------- provider interface ----------

    def assess(self, request: ScreeningRequest,
               sanctioned_addresses: set[str]) -> CheckResult:
        target = normalize_address(request.address)
        hits: list[Hit] = []
        payloads: list[bytes] = []
        try:
            payloads.append(self._address_hits(target, hits))
            if request.entity_name:
                payloads.append(self._name_hits(request.entity_name, hits))
            name_note = ("name match run" if request.entity_name
                         else "no entity name supplied — name leg not run")
        except Exception as exc:  # network/auth/rate-limit — inconclusive
            return CheckResult(
                check_id=self.check_id, ran=True, ok=False,
                inconclusive_reason=f"OpenSanctions query failed: {exc}")
        raw = b"".join(payloads)
        prov = Provenance(
            source_id=self.check_id,
            url=(f"{API_URL} (GET /search/{self._dataset}, "
                 f"POST /match/{self._dataset})"),
            fetched_at=utcnow_iso(),
            sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
            detail=(f"dataset '{self._dataset}'; address search + {name_note}"))
        return CheckResult(
            check_id=self.check_id, ran=True, ok=True, hits=hits,
            provenance=prov,
            notes=(f"OpenSanctions '{self._dataset}': {len(hits)} hit(s) "
                   f"({name_note})."))
