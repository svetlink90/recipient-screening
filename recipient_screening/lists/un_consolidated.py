"""UN Security Council Consolidated List XML parser.

The UN list rarely carries structured crypto-address fields; names and
aliases are the primary match surface, and free-text fields are scanned for
embedded addresses. Namespace-agnostic.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from ..matching import extract_addresses_from_text
from .base import ListEntry
from .xmlutil import children, child_text, local


def _texts(el: ET.Element, container: str, item: str) -> list[str]:
    out = []
    for cont in children(el, container):
        for child in children(cont, item):
            if child.text and child.text.strip():
                out.append(child.text.strip())
    return out


def parse(path: Path, list_id: str) -> list[ListEntry]:
    entries: list[ListEntry] = []
    for _event, el in ET.iterparse(str(path), events=("end",)):
        tag = local(el.tag)
        if tag == "ENTITY":
            ref = child_text(el, "REFERENCE_NUMBER") or ""
            names = []
            name_el = child_text(el, "NAME")
            if name_el:
                names.append(name_el)
            names += _texts(el, "ALIAS", "NAME")
            comments = child_text(el, "COMMENTS1") or ""
            entries.append(ListEntry(
                list_id=list_id, entry_id=ref, names=names,
                addresses=extract_addresses_from_text(comments),
                remarks=comments,
                verbatim={"referenceNumber": ref, "names": names,
                          "comments": comments},
            ))
            el.clear()
        elif tag == "INDIVIDUAL":
            ref = child_text(el, "REFERENCE_NUMBER") or ""
            parts = [child_text(el, n) or "" for n in
                     ("FIRST_NAME", "SECOND_NAME", "THIRD_NAME", "FOURTH_NAME")]
            primary = " ".join(p for p in parts if p)
            names = [primary] if primary else []
            names += _texts(el, "INDIVIDUAL_ALIAS", "ALIAS_NAME")
            designation = "; ".join(_texts(el, "DESIGNATION", "VALUE"))
            comments = child_text(el, "COMMENTS1") or ""
            entries.append(ListEntry(
                list_id=list_id, entry_id=ref, names=names,
                addresses=extract_addresses_from_text(comments),
                remarks=comments, programs=[designation] if designation else [],
                verbatim={"referenceNumber": ref, "names": names,
                          "designation": designation, "comments": comments},
            ))
            el.clear()
    return entries
