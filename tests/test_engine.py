from recipient_screening.engine import Engine
from recipient_screening.models import (HitKind, ScreeningRequest,
                                        VerdictStatus)
from recipient_screening.report import write_reports

from helpers import CLEAN_EVM, SANCTIONED_EVM, make_config


def _engine(tmp_path, **kwargs):
    return Engine(make_config(tmp_path, **kwargs))


def test_sanctioned_address_is_stop_hit(tmp_path):
    eng = _engine(tmp_path)
    report = eng.screen(ScreeningRequest(address=SANCTIONED_EVM))
    assert report.verdict.status == VerdictStatus.STOP_HIT
    kinds = {h.kind for c in report.checks for h in c.hits}
    assert HitKind.ADDRESS_EXACT in kinds
    # Every required list still ran — no inconclusive checks
    assert all(c.ok for c in report.checks)


def test_sanctioned_address_matches_case_insensitively(tmp_path):
    eng = _engine(tmp_path)
    report = eng.screen(ScreeningRequest(address=SANCTIONED_EVM.lower()))
    assert report.verdict.status == VerdictStatus.STOP_HIT


def test_clean_address_and_entity_is_clear(tmp_path):
    eng = _engine(tmp_path)
    report = eng.screen(ScreeningRequest(
        address=CLEAN_EVM, entity_name="Harmless Counterparty Ltd"))
    assert report.verdict.status == VerdictStatus.CLEAR
    assert not any(c.hits for c in report.checks)


def test_strong_entity_name_match_is_stop_hit(tmp_path):
    eng = _engine(tmp_path)
    report = eng.screen(ScreeningRequest(
        address=CLEAN_EVM, entity_name="Lazarus Group"))
    assert report.verdict.status == VerdictStatus.STOP_HIT
    kinds = {h.kind for c in report.checks for h in c.hits}
    assert HitKind.NAME_STRONG in kinds


def test_review_band_entity_name_is_stop_inconclusive(tmp_path):
    eng = _engine(tmp_path)
    report = eng.screen(ScreeningRequest(
        address=CLEAN_EVM, entity_name="Lazarus Gruop"))  # typo
    assert report.verdict.status == VerdictStatus.STOP_INCONCLUSIVE
    kinds = {h.kind for c in report.checks for h in c.hits}
    assert HitKind.NAME_POSSIBLE in kinds
    assert HitKind.NAME_STRONG not in kinds


def test_missing_required_list_is_stop_inconclusive(tmp_path):
    eng = _engine(tmp_path, ofac_url="file:///nonexistent/ofac.xml")
    report = eng.screen(ScreeningRequest(address=CLEAN_EVM))
    assert report.verdict.status == VerdictStatus.STOP_INCONCLUSIVE
    assert any("could not fetch" in (c.inconclusive_reason or "")
               for c in report.checks)


def test_known_mixer_address_is_stop_hit(tmp_path):
    eng = _engine(tmp_path)
    report = eng.screen(ScreeningRequest(
        address="0x12D66f87A04A9E220743712cE6d9bB1B5616B8Fc"))  # TC 0.1 ETH
    assert report.verdict.status == VerdictStatus.STOP_HIT
    assert any(h.kind == HitKind.RISK_FLAG
               for c in report.checks for h in c.hits)


def test_report_files_written_with_provenance(tmp_path):
    eng = _engine(tmp_path)
    report = eng.screen(ScreeningRequest(
        address=SANCTIONED_EVM, entity_name="Lazarus Group",
        context="test run"))
    md, js = write_reports(report, eng.reports_dir, "Checklist v1, item 9")
    text = md.read_text()
    assert "STOP_HIT" in text
    assert "Test Security Contact" in text
    assert "sha256" in text.lower()
    assert SANCTIONED_EVM[:10] in md.name
    import json
    payload = json.loads(js.read_text())
    assert payload["verdict"]["status"] == "STOP_HIT"


def test_stale_cache_fallback_still_conclusive(tmp_path):
    """A cached list stays usable when refresh fails (provenance preserved)."""
    eng = _engine(tmp_path)
    eng.screen(ScreeningRequest(address=CLEAN_EVM))  # populate cache
    # Point OFAC at a dead URL — refresh will fail, cache must be used.
    eng.cfg["lists"][0]["url"] = "file:///nonexistent/ofac.xml"
    eng.max_age = 0  # force refresh attempt
    report = eng.screen(ScreeningRequest(address=SANCTIONED_EVM))
    assert report.verdict.status == VerdictStatus.STOP_HIT
    ofac = next(c for c in report.checks if c.check_id == "list:ofac_sdn")
    assert ofac.ok and "cached copy" in ofac.notes
