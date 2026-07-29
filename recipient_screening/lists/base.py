"""Sanctions list interface and shared entry record."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ListEntry:
    """One sanctions-list entry, normalized across publishers."""

    list_id: str
    entry_id: str            # publisher-native identifier
    names: list[str] = field(default_factory=list)      # primary + aliases
    addresses: list[str] = field(default_factory=list)  # crypto addresses
    programs: list[str] = field(default_factory=list)
    remarks: str = ""
    verbatim: dict = field(default_factory=dict)
