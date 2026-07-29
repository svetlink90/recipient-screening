"""Namespace-agnostic XML helpers.

Official list publishers attach default namespaces without notice (OFAC SDN
does; UN does not). ElementTree's findall('./x') silently matches nothing
under a default namespace — which would turn a schema change into a silent
'no hits' screen. These helpers match on local names only.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def children(el: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in el if local(c.tag) == name]


def child(el: ET.Element, name: str) -> ET.Element | None:
    for c in el:
        if local(c.tag) == name:
            return c
    return None


def child_text(el: ET.Element, name: str) -> str | None:
    c = child(el, name)
    if c is None or c.text is None:
        return None
    text = c.text.strip()
    return text or None
