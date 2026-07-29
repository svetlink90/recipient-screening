from recipient_screening.matching import (extract_addresses_from_text,
                                          name_similarity, normalize_address,
                                          normalize_name, token_subset)


def test_evm_address_normalizes_case():
    assert normalize_address("0x098B716B8Aaf21512996dC57EB0615e2383E2f96") == \
        "0x098b716b8aaf21512996dc57eb0615e2383e2f96"


def test_btc_address_case_preserved():
    assert normalize_address("1FMjnc6kvhX5RLQfBpD2n4EXAMPLE") == \
        "1FMjnc6kvhX5RLQfBpD2n4EXAMPLE"


def test_name_normalize_strips_diacritics_and_punct():
    assert normalize_name("Müller & Söhne, GmbH") == "MULLER SOHNE GMBH"


def test_name_similarity_exact_after_normalization():
    assert name_similarity("Lazarus Group", "LAZARUS  GROUP") == 1.0


def test_name_similarity_word_order():
    assert name_similarity("Group Lazarus", "Lazarus Group") == 1.0


def test_name_similarity_typo_in_review_band():
    sim = name_similarity("Lazarus Gruop", "Lazarus Group")
    assert 0.85 <= sim < 0.95


def test_name_similarity_unrelated_is_low():
    assert name_similarity("Acme Trading Ltd", "Lazarus Group") < 0.7


def test_token_subset():
    assert token_subset("Lazarus Group", "The Lazarus Group International")
    assert not token_subset("Lazarus", "Lazarus Group")  # single token: no


def test_extract_addresses_from_text():
    text = ("Wallet 0x098B716B8Aaf21512996dC57EB0615e2383E2f96 and "
            "btc bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh")
    found = extract_addresses_from_text(text)
    assert "0x098b716b8aaf21512996dc57eb0615e2383e2f96" in found
    assert any(a.startswith("bc1") for a in found)
