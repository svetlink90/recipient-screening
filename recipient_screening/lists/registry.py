"""List registry: format string -> parser."""

from __future__ import annotations

from pathlib import Path

from . import eu_fsd, eu_fsd_csv, ofac_sdn, uk_ofsi, un_consolidated
from .base import ListEntry

PARSERS = {
    "ofac_xml": ofac_sdn.parse,
    "un_xml": un_consolidated.parse,
    "eu_fsd_xml": eu_fsd.parse,
    "eu_fsd_csv": eu_fsd_csv.parse,
    "uk_ofsi_xml": uk_ofsi.parse,
}


def parse_list(fmt: str, path: Path, list_id: str) -> list[ListEntry]:
    if fmt not in PARSERS:
        raise ValueError(f"Unknown list format: {fmt}")
    return PARSERS[fmt](path, list_id)
