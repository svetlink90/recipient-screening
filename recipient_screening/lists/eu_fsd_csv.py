"""EU FSD CSV v1.1 parser ("full consolidated list", semicolon-delimited).

The EU FSD download page offers the full list as XML and as CSV v1.0/v1.1.
v1.1 is the modern export: one row per name-alias/address/birth/ID
combination, grouped by Entity_LogicalId. Crypto addresses, when present,
surface in Identification_* fields or free text — scanned with the same
heuristic as the XML parser.

Download (browser only — the site blocks scripted fetches with 403):
https://webgate.ec.europa.eu/fsd/fsf  →  "Full list" → CSV v1.1
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..matching import extract_addresses_from_text
from .base import ListEntry

# Columns scanned for crypto addresses and kept as verbatim evidence.
_ID_COLS = ("Identification_Number", "Identification_TypeDescription",
            "Identification_LatinNumber", "Identification_Remark",
            "Entity_DesignationDetails", "Entity_Remark")


def _name_from(row: dict) -> str:
    whole = (row.get("NameAlias_WholeName") or "").strip()
    if whole:
        return whole
    parts = [(row.get(k) or "").strip() for k in
             ("NameAlias_FirstName", "NameAlias_MiddleName",
              "NameAlias_LastName")]
    return " ".join(p for p in parts if p)


def parse(path: Path, list_id: str) -> list[ListEntry]:
    grouped: dict[str, ListEntry] = {}
    free_text: dict[str, list[str]] = {}
    # Rows repeat per attribute; utf-8-sig strips the BOM.
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            lid = (row.get("Entity_LogicalId") or "").strip()
            if not lid:
                continue
            entry = grouped.get(lid)
            if entry is None:
                ref = (row.get("Entity_EU_ReferenceNumber") or "").strip()
                programme = (row.get("Entity_Regulation_Programme")
                             or "").strip()
                reg_no = (row.get("Entity_Regulation_NumberTitle")
                          or "").strip()
                entry = ListEntry(
                    list_id=list_id,
                    entry_id=ref or lid,
                    programs=[p for p in (programme, reg_no) if p],
                    remarks=(row.get("Entity_Remark") or "").strip(),
                    verbatim={
                        "logicalId": lid,
                        "euReferenceNumber": ref,
                        "subjectType": (row.get("Entity_SubjectType")
                                        or "").strip(),
                        "programme": programme,
                        "regulation": reg_no,
                    })
                grouped[lid] = entry
                free_text[lid] = []
            name = _name_from(row)
            if name and name not in entry.names:
                entry.names.append(name)
            for col in _ID_COLS:
                v = (row.get(col) or "").strip()
                if v:
                    free_text[lid].append(v)
    entries: list[ListEntry] = []
    for lid, entry in grouped.items():
        text = " | ".join(free_text[lid])
        entry.addresses = extract_addresses_from_text(text)
        if text and not entry.remarks:
            entry.remarks = text[:500]
        entry.verbatim["names"] = entry.names
        entries.append(entry)
    return entries


def publish_date(path: Path) -> str:
    """fileGenerationDate from the header row (evidence detail)."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        row = next(csv.DictReader(f, delimiter=";"), None)
    return (row or {}).get("fileGenerationDate", "").strip()
