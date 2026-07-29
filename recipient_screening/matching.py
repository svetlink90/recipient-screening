"""Address and name normalization/matching.

Conservative by design: a false negative (missed hit) is worse than a false
positive (unnecessary escalation). False positives resolve to
STOP_INCONCLUSIVE and human review; false negatives lose funds.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

EVM_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
# Free-text scanners for remarks/comment fields on name-only lists.
EVM_IN_TEXT_RE = re.compile(r"0x[0-9a-fA-F]{40}")
BTC_IN_TEXT_RE = re.compile(r"\b(bc1[a-z0-9]{25,62}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b")


def normalize_address(address: str) -> str:
    """Normalize for exact matching. EVM addresses are case-insensitive;
    everything else (BTC, XMR, TRON...) is case-sensitive."""
    a = address.strip()
    if EVM_ADDRESS_RE.match(a):
        return a.lower()
    return a


def extract_addresses_from_text(text: str) -> list[str]:
    """Pull candidate crypto addresses out of free text (remarks fields)."""
    found = {m.group(0).lower() for m in EVM_IN_TEXT_RE.finditer(text)}
    found |= {m.group(0) for m in BTC_IN_TEXT_RE.finditer(text)}
    return sorted(found)


def normalize_name(name: str) -> str:
    n = unicodedata.normalize("NFKD", name)
    n = "".join(c for c in n if not unicodedata.combining(c))
    n = n.upper()
    n = re.sub(r"[^A-Z0-9 ]+", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def name_similarity(a: str, b: str) -> float:
    """Best of direct and token-sorted similarity (catches word-order
    variants like 'Lazarus Group' vs 'Group Lazarus')."""
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return 0.0
    direct = SequenceMatcher(None, na, nb).ratio()
    ta = " ".join(sorted(na.split()))
    tb = " ".join(sorted(nb.split()))
    return max(direct, SequenceMatcher(None, ta, tb).ratio())


def token_subset(query: str, candidate: str) -> bool:
    """All query tokens appear in the candidate (e.g. 'Lazarus' inside a
    longer alias). Treated as a review-band signal, never a strong hit."""
    q = set(normalize_name(query).split())
    c = set(normalize_name(candidate).split())
    return len(q) >= 2 and q <= c
