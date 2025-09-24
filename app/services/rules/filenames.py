# Path: app/services/rules/filenames.py
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import List, Dict

FUTURE_DIR = Path("future_dev")
FUTURE_DB = FUTURE_DIR / "todos.json"
REPORT_MD = FUTURE_DIR / "todos_report.md"
TEMPLATE_MD = FUTURE_DIR / "todos_report_template.md"

TODO_RX = re.compile(r"//\s*(TODO|FIXME)\b(.*)", re.IGNORECASE)

def _load_index() -> List[Dict]:
    if FUTURE_DB.exists():
        try:
            return json.loads(FUTURE_DB.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def _save_index(idx: List[Dict]) -> None:
    FUTURE_DIR.mkdir(parents=True, exist_ok=True)
    FUTURE_DB.write_text(json.dumps(idx, indent=2), encoding="utf-8")

def _generate_report(idx: List[Dict]) -> None:
    FUTURE_DIR.mkdir(parents=True, exist_ok=True)
    if TEMPLATE_MD.exists():
        head = TEMPLATE_MD.read_text(encoding="utf-8")
    else:
        head = "# TODO/FIXME Report\n\n"
    lines = [head.strip(), ""]
    total = 0
    for entry in idx:
        total += entry.get("count", 0)
    lines.append(f"**Total TODO/FIXME items:** {total}\n")
    for entry in idx:
        if entry.get("items"):
            lines.append(f"## {entry['file']}")
            for it in entry["items"]:
                lines.append(f"- L{it['line']}: {it['text']}")
            lines.append("")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

def flag_valuable_content(path: str, code: str) -> None:
    """
    Extract //TODO and //FIXME (with line numbers), save to future_dev/{basename}.js,
    append a lowdb-style index, and regenerate a human report.
    """
    FUTURE_DIR.mkdir(parents=True, exist_ok=True)
    lines_found: List[Dict] = []
    for i, raw in enumerate((code or "").splitlines(), start=1):
        m = TODO_RX.search(raw)
        if m:
            lines_found.append({"line": i, "text": raw.strip()})

    base = Path(path).name
    if lines_found:
        out_file = FUTURE_DIR / f"{base}"
        header = f"// Extracted TODO/FIXME from {path}\n"
        out_file.write_text(header + "\n".join([f"// L{it['line']}: {it['text']}" for it in lines_found]) + "\n", encoding="utf-8")

    idx = _load_index()
    idx.append({"file": path, "count": len(lines_found), "items": lines_found})
    _save_index(idx)
    _generate_report(idx)
