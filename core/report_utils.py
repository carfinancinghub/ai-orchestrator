
"""
Path: core/report_utils.py
Helpers to list/load orchestrator run reports.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, Optional
import json


def latest_report_path(reports_dir: Path) -> Optional[Path]:
    if not reports_dir.exists():
        return None
    items = sorted(reports_dir.glob("run-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return items[0] if items else None


def load_report_by_id(reports_dir: Path, run_id: str) -> Optional[Dict[str, object]]:
    p = reports_dir / f"{run_id}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))

