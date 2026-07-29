"""Screening engine: orchestrates lists + risk providers into a Report."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from . import provenance as prov
from .lists.registry import parse_list
from .matching import (name_similarity, normalize_address, token_subset)
from .models import (CheckResult, Hit, HitKind, Report, ScreeningRequest)
from .provenance import utcnow_iso
from .risk.chainabuse import ChainabuseProvider
from .risk.etherscan_proximity import EtherscanProximityProvider
from .risk.known_sets import KnownSetsProvider
from .risk.opensanctions import OpenSanctionsProvider
from .verdict import compute_verdict


class Engine:
    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path).resolve()
        self.root = self.config_path.parent
        with self.config_path.open("rb") as f:
            self.cfg = tomllib.load(f)
        scr = self.cfg["screening"]
        self.data_dir = (self.root / scr["data_dir"]).resolve()
        self.reports_dir = (self.root / scr["reports_dir"]).resolve()
        self.max_age = float(scr["max_list_age_hours"])
        self.hit_threshold = float(scr["name_hit_threshold"])
        self.review_threshold = float(scr["name_review_threshold"])
        self.security_contact = self.cfg["agent"]["security_contact"]

    # ---------- sanctions lists ----------

    def _cache_file(self, lst: dict) -> Path:
        ext = ".csv" if str(lst.get("format", "")).endswith("_csv") else ".xml"
        return self.data_dir / f"{lst['id']}{ext}"

    def _ensure_fresh(self, lst: dict) -> tuple[Path, object, str]:
        """Return (cache_file, meta, note). If a refresh fails but a cache
        exists, fall back to the stale cache with an explicit note — the
        screen stays conclusive against a known, provenance-stamped version.
        No cache + failed fetch is the only inconclusive path."""
        cache_file = self._cache_file(lst)
        meta = prov.load_meta(cache_file)
        if meta is None or prov.cache_age_hours(meta) > self.max_age:
            try:
                meta = prov.fetch_to_cache(lst["id"], lst["url"], cache_file)
            except Exception:
                if meta is None:
                    raise
                return cache_file, meta, (
                    f"refresh failed; screened against cached copy from "
                    f"{meta.fetched_at} (sha256 {meta.sha256[:12]}…)")
        return cache_file, meta, ""

    def update_lists(self) -> list[tuple[str, str, str]]:
        """Force-refresh every configured list. Returns (id, status, detail)."""
        results = []
        for lst in self.cfg["lists"]:
            cache_file = self._cache_file(lst)
            try:
                meta = prov.fetch_to_cache(lst["id"], lst["url"], cache_file)
                results.append((lst["id"], "OK",
                                f"{meta.bytes} bytes, sha256 {meta.sha256[:12]}…"))
            except Exception as exc:
                results.append((lst["id"], "FAILED", str(exc)))
        return results

    def ingest_list(self, list_id: str, local_path: str | Path,
                    origin_note: str = "") -> tuple[str, str]:
        """Bring a manually downloaded list file into the cache.

        For sources that block automated fetches (e.g. EU FSD returns 403 to
        scripts), download the file in a browser or with the model's own web
        tools, then ingest it here. Provenance records the official URL plus
        the ingest path, so the evidence trail stays honest.
        """
        lst = next((l for l in self.cfg["lists"] if l["id"] == list_id), None)
        if lst is None:
            raise ValueError(f"unknown list id '{list_id}' — check config.toml")
        src = Path(local_path).expanduser().resolve()
        if not src.exists():
            raise FileNotFoundError(src)
        cache_file = self._cache_file(lst)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(src.read_bytes())
        meta = prov.Provenance(
            source_id=list_id,
            url=lst["url"],
            fetched_at=prov.utcnow_iso(),
            sha256=prov.sha256_file(cache_file),
            bytes=cache_file.stat().st_size,
            detail=(f"MANUALLY INGESTED from {src}"
                    + (f" — {origin_note}" if origin_note else "")
                    + " (verify download origin matches official URL)"),
            cache_path=str(cache_file),
        )
        import json as _json
        prov.meta_path(cache_file).write_text(_json.dumps(meta.__dict__,
                                                          indent=2))
        return meta.sha256, meta.detail

    def list_status(self) -> list[tuple[str, str, str]]:
        out = []
        for lst in self.cfg["lists"]:
            cache_file = self._cache_file(lst)
            meta = prov.load_meta(cache_file)
            if meta is None:
                out.append((lst["id"], "MISSING", "no cache — run `update`"))
            else:
                age = prov.cache_age_hours(meta)
                out.append((lst["id"],
                            "STALE" if age > self.max_age else "FRESH",
                            f"fetched {meta.fetched_at} ({age:.1f}h old), "
                            f"sha256 {meta.sha256[:12]}…"))
        return out

    def _screen_list(self, lst: dict, request: ScreeningRequest,
                     sanctioned_addresses: set[str]) -> CheckResult:
        check_id = f"list:{lst['id']}"
        stale_note = ""
        try:
            cache_file, meta, stale_note = self._ensure_fresh(lst)
        except Exception as exc:
            return CheckResult(
                check_id=check_id, ran=True, ok=False,
                inconclusive_reason=f"could not fetch {lst['name']}: {exc}")
        try:
            entries = parse_list(lst["format"], cache_file, lst["id"])
        except Exception as exc:
            return CheckResult(
                check_id=check_id, ran=True, ok=False,
                inconclusive_reason=f"could not parse {lst['name']}: {exc}",
                provenance=meta)
        if not entries:
            # A schema change can turn a parse into a silent empty result,
            # which would masquerade as a clean screen. Never allow that.
            return CheckResult(
                check_id=check_id, ran=True, ok=False,
                inconclusive_reason=(
                    f"parser produced 0 entries from {lst['name']} — "
                    "the publisher's schema may have changed; investigate "
                    "before relying on any CLEAR result"),
                provenance=meta)
        target = normalize_address(request.address)
        hits: list[Hit] = []
        for e in entries:
            for addr in e.addresses:
                norm = normalize_address(addr)
                sanctioned_addresses.add(norm)
                if norm == target:
                    hits.append(Hit(
                        kind=HitKind.ADDRESS_EXACT, source_id=lst["id"],
                        matched_value=addr,
                        entry_name=e.names[0] if e.names else "(unnamed)",
                        entry_reference=e.entry_id,
                        detail=f"Exact address match on {lst['name']}.",
                        verbatim=e.verbatim))
            if request.entity_name:
                for name in e.names:
                    sim = name_similarity(request.entity_name, name)
                    if sim >= self.hit_threshold:
                        hits.append(Hit(
                            kind=HitKind.NAME_STRONG, source_id=lst["id"],
                            matched_value=name,
                            entry_name=e.names[0] if e.names else name,
                            entry_reference=e.entry_id,
                            detail=f"Name similarity {sim:.2f} "
                                   f"(>= {self.hit_threshold}) on {lst['name']}.",
                            verbatim=e.verbatim))
                        break
                    if sim >= self.review_threshold or token_subset(
                            request.entity_name, name):
                        hits.append(Hit(
                            kind=HitKind.NAME_POSSIBLE, source_id=lst["id"],
                            matched_value=name,
                            entry_name=e.names[0] if e.names else name,
                            entry_reference=e.entry_id,
                            detail=f"Name similarity {sim:.2f} in review band "
                                   f"({self.review_threshold}-"
                                   f"{self.hit_threshold}) on {lst['name']}. "
                                   "Human disambiguation required.",
                            verbatim=e.verbatim))
                        break
        return CheckResult(
            check_id=check_id, ran=True, ok=True, hits=hits,
            provenance=meta,
            notes=(f"{len(entries)} entries screened from {lst['name']}."
                   + (" " + stale_note if stale_note else "")))

    # ---------- risk providers ----------

    def _risk_providers(self):
        providers = []
        risk_cfg = self.cfg.get("risk", {})
        ks = risk_cfg.get("known_sets", {})
        if ks.get("enabled", True):
            providers.append((KnownSetsProvider(), bool(ks.get("required", True))))
        cb = risk_cfg.get("chainabuse", {})
        if cb.get("enabled", False):
            key = os.environ.get(cb.get("api_key_env", "CHAINABUSE_API_KEY"), "")
            secret = os.environ.get(cb.get("api_secret_env", "CHAINABUSE_API_SECRET"), "")
            if key and secret:
                providers.append((ChainabuseProvider(key, secret),
                                  bool(cb.get("required", False))))
            else:
                providers.append((_MissingCreds("chainabuse",
                                                "CHAINABUSE_API_KEY/SECRET not set"),
                                  bool(cb.get("required", False))))
        es = risk_cfg.get("etherscan_proximity", {})
        if es.get("enabled", False):
            key = es.get("api_key") or os.environ.get(
                es.get("api_key_env", "ETHERSCAN_API_KEY"), "")
            if key:
                providers.append((EtherscanProximityProvider(
                    key, int(es.get("lookback_txs", 200))),
                    bool(es.get("required", False))))
            else:
                providers.append((_MissingCreds("etherscan_proximity",
                                                "ETHERSCAN_API_KEY not set"),
                                  bool(es.get("required", False))))
        osan = risk_cfg.get("opensanctions", {})
        if osan.get("enabled", False):
            key = osan.get("api_key") or os.environ.get(
                osan.get("api_key_env", "OPENSANCTIONS_API_KEY"), "")
            if key:
                providers.append((OpenSanctionsProvider(
                    key,
                    dataset=str(osan.get("dataset", "sanctions")),
                    hit_threshold=float(osan.get("name_hit_threshold", 0.90)),
                    review_threshold=float(
                        osan.get("name_review_threshold", 0.70))),
                    bool(osan.get("required", False))))
            else:
                providers.append((_MissingCreds("opensanctions",
                                                "OPENSANCTIONS_API_KEY not set"),
                                  bool(osan.get("required", False))))
        return providers

    # ---------- main entry ----------

    def screen(self, request: ScreeningRequest) -> Report:
        checks: list[CheckResult] = []
        sanctioned_addresses: set[str] = set()
        required_ids: set[str] = set()

        for lst in self.cfg["lists"]:
            if lst.get("required", True):
                required_ids.add(f"list:{lst['id']}")
            checks.append(self._screen_list(lst, request, sanctioned_addresses))

        for provider, required in self._risk_providers():
            if required:
                required_ids.add(provider.check_id)
            checks.append(provider.assess(request, sanctioned_addresses))

        verdict = compute_verdict(checks, self.security_contact, required_ids)
        return Report(request=request, screened_at=utcnow_iso(),
                      checks=checks, verdict=verdict)


class _MissingCreds:
    """Placeholder provider when a key is configured but absent."""

    def __init__(self, check_id: str, reason: str):
        self.check_id = check_id
        self._reason = reason

    def assess(self, request, sanctioned_addresses):
        return CheckResult(check_id=self.check_id, ran=False, ok=False,
                           inconclusive_reason=self._reason)
