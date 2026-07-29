"""OFAC SDN / Consolidated XML parser.

Crypto addresses live in <idList><id> elements whose <idType> starts with
'Digital Currency Address'. Both sdn.xml and consolidated.xml share this
schema, so one parser serves both. Namespace-agnostic (OFAC publishes with
a default namespace).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from .base import ListEntry
from .xmlutil import child, children, child_text, local

DC_PREFIX = "digital currency address"


def _join_name(first: str | None, last: str | None) -> str:
    parts = [p for p in (first, last) if p]
    return " ".join(parts)


def parse(path: Path, list_id: str) -> list[ListEntry]:
    entries: list[ListEntry] = []
    for _event, el in ET.iterparse(str(path), events=("end",)):
        if local(el.tag) != "sdnEntry":
            continue
        uid = child_text(el, "uid") or ""
        primary = _join_name(child_text(el, "firstName"),
                             child_text(el, "lastName"))
        sdn_type = child_text(el, "sdnType") or ""
        names = [primary] if primary else []
        for aka_list in children(el, "akaList"):
            for aka in children(aka_list, "aka"):
                alias = _join_name(child_text(aka, "firstName"),
                                   child_text(aka, "lastName"))
                if alias:
                    names.append(alias)
        addresses: list[str] = []
        for id_list in children(el, "idList"):
            for id_el in children(id_list, "id"):
                id_type = (child_text(id_el, "idType") or "").lower()
                id_number = child_text(id_el, "idNumber") or ""
                if id_type.startswith(DC_PREFIX) and id_number:
                    addresses.append(id_number)
        programs = []
        for prog_list in children(el, "programList"):
            for p in children(prog_list, "program"):
                if p.text and p.text.strip():
                    programs.append(p.text.strip())
        remarks = child_text(el, "remarks") or ""
        entries.append(ListEntry(
            list_id=list_id,
            entry_id=uid,
            names=names,
            addresses=addresses,
            programs=programs,
            remarks=remarks,
            verbatim={
                "uid": uid,
                "sdnType": sdn_type,
                "primaryName": primary,
                "programs": programs,
                "remarks": remarks,
                "digitalCurrencyAddresses": addresses,
            },
        ))
        el.clear()
    return entries


def publish_date(path: Path) -> str:
    """Best-effort <Publish_Date> extraction for provenance detail."""
    try:
        for _event, el in ET.iterparse(str(path), events=("end",)):
            tag = local(el.tag)
            if tag == "Publish_Date" and el.text:
                return el.text.strip()
            if tag == "sdnEntry":
                return ""  # passed the header without finding it
    except ET.ParseError:
        pass
    return ""
