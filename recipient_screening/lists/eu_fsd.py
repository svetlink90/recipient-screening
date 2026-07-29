"""EU Financial Sanctions Database (FSD) XML parser.

Parsed defensively via element/attribute names because the FSD schema has
shifted between exports. Names come from nameAlias elements; identification
and remark free-text is scanned for crypto addresses.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from ..matching import extract_addresses_from_text
from .base import ListEntry


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def parse(path: Path, list_id: str) -> list[ListEntry]:
    entries: list[ListEntry] = []
    current: dict | None = None
    for event, el in ET.iterparse(str(path), events=("end",)):
        tag = _local(el.tag)
        if tag == "sanctionsentity":
            names: list[str] = []
            free_text: list[str] = []
            entry_id = el.attrib.get("logicalId") or el.attrib.get("id") or ""
            regulation = ""
            for child in el.iter():
                ctag = _local(child.tag)
                if ctag == "namealias":
                    whole = child.attrib.get("wholeName")
                    if whole and whole.strip():
                        names.append(whole.strip())
                        continue
                    parts = [child.attrib.get(k, "") for k in
                             ("firstName", "middleName", "lastName")]
                    joined = " ".join(p.strip() for p in parts if p.strip())
                    if joined:
                        names.append(joined)
                elif ctag == "identification":
                    for v in child.attrib.values():
                        if v:
                            free_text.append(v)
                elif ctag in ("remark", "regulation"):
                    if child.text and child.text.strip():
                        free_text.append(child.text.strip())
                        if ctag == "regulation":
                            regulation = child.text.strip()
            if names or free_text:
                remarks = " | ".join(free_text)
                entries.append(ListEntry(
                    list_id=list_id, entry_id=entry_id, names=names,
                    addresses=extract_addresses_from_text(remarks),
                    remarks=remarks,
                    programs=[regulation] if regulation else [],
                    verbatim={"logicalId": entry_id, "names": names,
                              "regulation": regulation},
                ))
            el.clear()
    return entries
