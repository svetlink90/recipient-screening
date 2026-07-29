from pathlib import Path

from recipient_screening.lists import (eu_fsd, eu_fsd_csv, ofac_sdn,
                                       uk_ofsi, un_consolidated)

FIXTURES = Path(__file__).parent / "fixtures"


def test_ofac_parses_digital_currency_addresses():
    entries = ofac_sdn.parse(FIXTURES / "ofac_fixture.xml", "ofac_sdn")
    assert len(entries) == 2
    lazarus = entries[0]
    assert lazarus.entry_id == "99901"
    assert "LAZARUS GROUP" in lazarus.names
    assert "APT38" in lazarus.names
    assert "0x098B716B8Aaf21512996dC57EB0615e2383E2f96" in lazarus.addresses
    assert "1FMjnc6kvhX5RLQfBpD2n4EXAMPLE" in lazarus.addresses
    assert lazarus.programs == ["DPRK3"]
    assert lazarus.verbatim["sdnType"] == "Entity"


def test_ofac_publish_date():
    assert ofac_sdn.publish_date(FIXTURES / "ofac_fixture.xml") == "07/28/2026"


def test_un_parses_entities_and_individuals():
    entries = un_consolidated.parse(FIXTURES / "un_fixture.xml", "un_consolidated")
    assert len(entries) == 2
    entity = entries[0]
    assert entity.entry_id == "KPe.999"
    assert "LAZARUS GROUP" in entity.names and "APT38" in entity.names
    individual = entries[1]
    assert "Jane Doe" in individual.names
    assert individual.programs == ["Fixture role"]


def test_eu_parses_wholename_and_scans_free_text():
    entries = eu_fsd.parse(FIXTURES / "eu_fixture.xml", "eu_fsd")
    assert len(entries) == 2
    lazarus = entries[0]
    assert "LAZARUS GROUP" in lazarus.names
    assert "0x098b716b8aaf21512996dc57eb0615e2383e2f96" in lazarus.addresses
    acme = entries[1]
    assert "ACME TRADING LTD" in acme.names


def test_eu_csv_v11_groups_aliases_and_scans_ids():
    entries = eu_fsd_csv.parse(FIXTURES / "eu_csv_fixture.csv", "eu_fsd")
    assert len(entries) == 3
    lazarus = next(e for e in entries if e.entry_id == "EU.99.1")
    assert "LAZARUS GROUP" in lazarus.names
    assert "APT38" in lazarus.names  # alias row merged into one entry
    assert "0x098b716b8aaf21512996dc57eb0615e2383e2f96" in lazarus.addresses
    assert "DPRK" in lazarus.programs
    person = next(e for e in entries if e.entry_id == "EU.99.2")
    assert person.names == ["Jane X Doe"]  # first/middle/last fallback
    assert eu_fsd_csv.publish_date(FIXTURES / "eu_csv_fixture.csv") == \
        "28/07/2026"


def test_uk_parses_grouped_targets_and_scans_text():
    entries = uk_ofsi.parse(FIXTURES / "uk_fixture.xml", "uk_ofsi")
    assert len(entries) == 2  # two GroupIDs, alias merged
    lazarus = entries[0]
    assert lazarus.entry_id == "99001"
    assert "LAZARUS GROUP" in lazarus.names
    assert "APT38" in lazarus.names
    assert "0x098b716b8aaf21512996dc57eb0615e2383e2f96" in lazarus.addresses
    acme = entries[1]
    assert "ACME TRADING LTD" in acme.names
