"""
Path: core/metrics.py
Purpose: Tiny metrics helper for audit/convert routes. Appends JSONL events.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{record}\n")


@dataclass
class ConvertEvent:
    kind: str
    src: str
    ok: bool
    reason: str | None
    ts_path: str | None
    root: str
    run_id: str | None = None
    at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["at"] = d["at"] or _ts()
        return d


@dataclass
class ConvertSummary:
    kind: str
    tried: int
    wrote: int
    outside_root: int
    missing: int
    quarantined: int
    root: str
    run_id: str | None = None
    at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["at"] = d["at"] or _ts()
        return d
