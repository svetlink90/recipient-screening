"""Caching and provenance for external sources.

A screening report is evidence. Every external input is stored on disk with
its URL, fetch timestamp, and SHA-256, so a report can be reproduced or
audited later ("which version of the SDN list said this address was clean?").
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .models import Provenance

USER_AGENT = "recipient-screening/0.1 (compliance evidence fetch)"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def meta_path(cache_file: Path) -> Path:
    return cache_file.with_suffix(cache_file.suffix + ".meta.json")


def load_meta(cache_file: Path) -> Provenance | None:
    mp = meta_path(cache_file)
    if not mp.exists() or not cache_file.exists():
        return None
    data = json.loads(mp.read_text())
    return Provenance(
        source_id=data["source_id"],
        url=data["url"],
        fetched_at=data["fetched_at"],
        sha256=data["sha256"],
        bytes=data["bytes"],
        detail=data.get("detail", ""),
        cache_path=str(cache_file),
    )


def fetch_to_cache(source_id: str, url: str, cache_file: Path,
                   timeout: int = 60) -> Provenance:
    """Download url to cache_file and write its provenance sidecar."""
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = resp.read()
    cache_file.write_bytes(payload)
    prov = Provenance(
        source_id=source_id,
        url=url,
        fetched_at=utcnow_iso(),
        sha256=sha256_file(cache_file),
        bytes=len(payload),
        cache_path=str(cache_file),
    )
    meta_path(cache_file).write_text(json.dumps(prov.__dict__, indent=2))
    return prov


def cache_age_hours(prov: Provenance) -> float:
    fetched = datetime.strptime(prov.fetched_at, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - fetched).total_seconds() / 3600.0
