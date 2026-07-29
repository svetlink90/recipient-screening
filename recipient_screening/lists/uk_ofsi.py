"""UK OFSI Consolidated List XML parser.

Real schema (verified against the live 2022-format ConList.xml): root is
<ArrayOfFinancialSanctionsTarget> under the HMT namespace; each flat
<FinancialSanctionsTarget> is ONE name record carrying GroupID, Name6
(surname/entity name), name1..name5, regime, and OtherInformation. Aliases
of one designated person are separate targets sharing a GroupID — so
targets are merged by GroupID here. OtherInformation free text is scanned
for crypto addresses.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from ..matching import extract_addresses_from_text
from .base import ListEntry
from .xmlutil import child_text, local

NAME_PART_FIELDS = ("name1", "name2", "name3", "name4", "name5", "Name6")


def _target_name(el: ET.Element) -> str:
    parts = []
    for f in NAME_PART_FIELDS:
        t = child_text(el, f)
        if t:
            parts.append(t)
    return " ".join(parts)


def parse(path: Path, list_id: str) -> list[ListEntry]:
    by_group: dict[str, ListEntry] = {}
    for _event, el in ET.iterparse(str(path), events=("end",)):
        if local(el.tag) != "FinancialSanctionsTarget":
            continue
        group_id = child_text(el, "GroupID") or ""
        name = _target_name(el)
        other_info = child_text(el, "OtherInformation") or ""
        statement = child_text(el, "UKStatementOfReasons") or ""
        regime = child_text(el, "RegimeName") or ""
        un_ref = child_text(el, "UNRef") or ""
        entry = by_group.get(group_id)
        if entry is None:
            entry = ListEntry(list_id=list_id, entry_id=group_id,
                              programs=[regime] if regime else [],
                              verbatim={"groupId": group_id, "names": []})
            by_group[group_id] = entry
        if name and name not in entry.names:
            entry.names.append(name)
            entry.verbatim["names"] = entry.names
        free_text = " | ".join(t for t in (other_info, statement) if t)
        for addr in extract_addresses_from_text(free_text):
            if addr not in entry.addresses:
                entry.addresses.append(addr)
        if free_text:
            entry.remarks = (entry.remarks + " | " + free_text).strip(" |")
        if un_ref:
            entry.verbatim["unRef"] = un_ref
        el.clear()
    return list(by_group.values())
