"""Offline tests for network-backed risk providers. HTTP is stubbed via
monkeypatched urllib.request.urlopen — no network, per project rules."""

import json
import urllib.request

import pytest

from recipient_screening.engine import Engine
from recipient_screening.models import (HitKind, ScreeningRequest,
                                        VerdictStatus)
from recipient_screening.risk.etherscan_proximity import (
    EtherscanProximityProvider)
from recipient_screening.risk.opensanctions import OpenSanctionsProvider

from helpers import CLEAN_EVM, SANCTIONED_EVM, make_config

TARGET = SANCTIONED_EVM
MIXER = "0x12D66f87A04A9E220743712cE6d9bB1B5616B8Fc"  # TC 0.1 ETH pool


class _Resp:
    def __init__(self, payload: bytes):
        self._p = payload

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _stub_urlopen(monkeypatch, handler):
    """handler(req) -> bytes; records requested URLs. Accepts both Request
    objects and plain URL strings (providers use both styles)."""
    calls: list[str] = []

    def fake_urlopen(req, timeout=None):
        calls.append(req.full_url if hasattr(req, "full_url") else req)
        return _Resp(handler(req))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return calls


# ---------------- OpenSanctions ----------------

OS_SEARCH_HIT = json.dumps({"results": [
    {"id": "ofac-abc", "caption": TARGET, "schema": "CryptoWallet",
     "datasets": ["us_ofac_sdn"],
     "properties": {"publicKey": [TARGET]}},
    {"id": "ja-mof-def", "caption": TARGET, "schema": "CryptoWallet",
     "datasets": ["jp_mof_sanctions"],
     "properties": {"publicKey": [TARGET.lower()]}},
]}).encode()

OS_SEARCH_FUZZY = json.dumps({"results": [
    {"id": "x1", "caption": TARGET, "schema": "CryptoWallet",
     "datasets": ["us_ofac_sdn"],
     "properties": {"publicKey": ["0x" + "0" * 40]}},
    {"id": "x2", "caption": "Lazarus Group", "schema": "Company",
     "datasets": ["us_ofac_sdn"], "properties": {}},
]}).encode()

OS_MATCH = json.dumps({"responses": {"q1": {"status": 200, "results": [
    {"id": "NK-1", "caption": "Lazarus Group", "schema": "Company",
     "score": 0.97, "datasets": ["us_ofac_sdn"]},
    {"id": "NK-2", "caption": "Lazarus Holdings", "schema": "Company",
     "score": 0.8, "datasets": ["jp_mof_sanctions"]},
    {"id": "NK-3", "caption": "Lazar It", "schema": "Person",
     "score": 0.4, "datasets": ["us_ofac_sdn"]},
]}}}).encode()

OS_MATCH_CLEAN = json.dumps(
    {"responses": {"q1": {"status": 200, "results": []}}}).encode()


def _os_provider():
    return OpenSanctionsProvider("test-key", hit_threshold=0.90,
                                 review_threshold=0.70)


def test_os_address_exact_hit(monkeypatch):
    def handler(req):
        return OS_SEARCH_HIT if "/search/" in req.full_url else OS_MATCH_CLEAN
    _stub_urlopen(monkeypatch, handler)
    res = _os_provider().assess(ScreeningRequest(address=TARGET), set())
    assert res.ok
    # Same wallet listed by two member lists merges into one hit.
    assert [h.kind for h in res.hits] == [HitKind.ADDRESS_EXACT]
    assert res.hits[0].verbatim["datasets"] == ["us_ofac_sdn",
                                                "jp_mof_sanctions"]
    assert "ofac-abc" in res.hits[0].entry_reference
    assert res.provenance and len(res.provenance.sha256) == 64


def test_os_fuzzy_search_results_ignored(monkeypatch):
    def handler(req):
        return OS_SEARCH_FUZZY if "/search/" in req.full_url \
            else OS_MATCH_CLEAN
    _stub_urlopen(monkeypatch, handler)
    res = _os_provider().assess(ScreeningRequest(address=TARGET), set())
    assert res.ok and not res.hits


def test_os_name_score_bands(monkeypatch):
    def handler(req):
        return OS_MATCH if "/match/" in req.full_url else OS_SEARCH_FUZZY
    _stub_urlopen(monkeypatch, handler)
    res = _os_provider().assess(
        ScreeningRequest(address=CLEAN_EVM, entity_name="Lazarus Group"),
        set())
    assert res.ok
    kinds = [h.kind for h in res.hits]
    assert HitKind.NAME_STRONG in kinds      # 0.97
    assert HitKind.NAME_POSSIBLE in kinds    # 0.80
    assert len(res.hits) == 2                # 0.40 below review band


def test_os_query_failure_is_inconclusive(monkeypatch):
    def handler(req):
        raise OSError("connection refused")
    _stub_urlopen(monkeypatch, handler)
    res = _os_provider().assess(ScreeningRequest(address=TARGET), set())
    assert res.ran and not res.ok
    assert "OpenSanctions query failed" in res.inconclusive_reason


def test_os_auth_header_sent(monkeypatch):
    seen = []

    def fake_urlopen(req, timeout=None):
        seen.append(req.get_header("Authorization"))
        return _Resp(OS_SEARCH_FUZZY)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    _os_provider().assess(ScreeningRequest(address=TARGET), set())
    assert seen == ["ApiKey test-key"]


def test_engine_stop_hit_via_opensanctions_name(monkeypatch, tmp_path):
    """Strong OpenSanctions name match escalates a clean-list screen."""
    def handler(req):
        return OS_MATCH if "/match/" in req.full_url else OS_SEARCH_FUZZY
    _stub_urlopen(monkeypatch, handler)
    cfg = make_config(tmp_path)
    cfg.write_text(cfg.read_text() + """
[risk.opensanctions]
enabled = true
required = false
api_key = "test-key"
dataset = "sanctions"
name_hit_threshold = 0.90
name_review_threshold = 0.70
""")
    report = Engine(cfg).screen(ScreeningRequest(
        address=CLEAN_EVM, entity_name="Lazarus Group"))
    assert report.verdict.status == VerdictStatus.STOP_HIT
    os_check = next(c for c in report.checks
                    if c.check_id == "opensanctions")
    assert os_check.ok and os_check.hits


# ---------------- Etherscan proximity (V2) ----------------

def _txlist(txs):
    return json.dumps({"status": "1", "message": "OK", "result": txs}).encode()


def test_etherscan_uses_v2_endpoint(monkeypatch):
    calls = _stub_urlopen(monkeypatch, lambda req: _txlist([]))
    res = EtherscanProximityProvider("k").assess(
        ScreeningRequest(address=CLEAN_EVM), set())
    assert res.ok
    assert "/v2/api" in calls[0] and "chainid=1" in calls[0]


def test_etherscan_flags_inbound_from_mixer(monkeypatch):
    txs = [{
        "from": MIXER.lower(), "to": CLEAN_EVM.lower(),
        "hash": "0xdead", "blockNumber": "123", "value": "1",
    }]
    _stub_urlopen(monkeypatch, lambda req: _txlist(txs))
    res = EtherscanProximityProvider("k").assess(
        ScreeningRequest(address=CLEAN_EVM), set())
    assert res.ok
    assert [h.kind for h in res.hits] == [HitKind.RISK_PROXIMITY]
    assert "Tornado Cash" in res.hits[0].entry_name


def test_etherscan_no_transactions_shape_is_conclusive_empty(monkeypatch):
    payload = json.dumps({"status": "0", "message": "No transactions found",
                          "result": "No transactions found"}).encode()
    _stub_urlopen(monkeypatch, lambda req: payload)
    res = EtherscanProximityProvider("k").assess(
        ScreeningRequest(address=CLEAN_EVM), set())
    assert res.ok and not res.hits and "0 recent txs" in res.notes


def test_etherscan_api_error_is_inconclusive(monkeypatch):
    def handler(req):
        raise OSError("rate limit / outage")
    _stub_urlopen(monkeypatch, handler)
    res = EtherscanProximityProvider("k").assess(
        ScreeningRequest(address=CLEAN_EVM), set())
    assert not res.ok and "Etherscan query failed" in res.inconclusive_reason


def test_etherscan_skips_non_ethereum():
    res = EtherscanProximityProvider("k").assess(
        ScreeningRequest(address="bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
                         chain="bitcoin"), set())
    assert not res.ran and res.ok  # noted as skipped, not a failure
