from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# --- config defaults ---
DOCS_ROOT = Path(r"C:\CFH\docs")
FRONTEND_ROOT = Path(r"C:\CFH\frontend")

@dataclass
class MoveSuggestion:
    src: Path
    dest: Path
    confidence: float
    reason: str
    doc_mirror: Optional[Path] = None

def _normpath(p: str | Path) -> Path:
    return Path(str(p)).expanduser().resolve()

def load_artifact(artifact_path: Path) -> Dict[str, Any]:
    data = json.loads(artifact_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Artifact must be a JSON object")
    return data

def iter_suggestions(data: Dict[str, Any]) -> Iterable[MoveSuggestion]:
    """
    Robustly extract suggestions from your current reviews schema:
    {
      "items": [
        {
          "src": "C:\\CFH\\frontend\\src\\components\\needsHome\\ARExperience.js",
          "suggested_moves": [
            {"dest": "C:\\CFH\\frontend\\src\\components\\seller\\ARExperience.js",
             "confidence": 0.7, "reason": "..."}
          ],
          "doc_mirror": "C:\\CFH\\docs\\frontend\\src\\components\\needsHome\\ARExperience.md"
        },
        ...
      ]
    }
    """
    items = data.get("items") or data.get("entries") or []
    if not isinstance(items, list):
        return

    for it in items:
        try:
            src = _normpath(it.get("src", ""))
            if not src:
                continue

            # take first suggestion if present
            moves = it.get("suggested_moves") or it.get("moves") or []
            m = moves[0] if isinstance(moves, list) and moves else None
            if not m:
                # nothing to route, still allow doc mirroring
                doc_mirror = it.get("doc_mirror")
                yield MoveSuggestion(src=src, dest=src, confidence=0.0, reason="no-suggestion", doc_mirror=_mirror_path_from_item(it))
                continue

            dest = _normpath(m.get("dest", ""))
            conf = float(m.get("confidence", 0.0))
            reason = str(m.get("reason", ""))

            doc_mirror = it.get("doc_mirror") or _mirror_path_from_item(it)  # fallback
            yield MoveSuggestion(src=src, dest=dest, confidence=conf, reason=reason, doc_mirror=_normpath(doc_mirror) if doc_mirror else None)
        except Exception:
            # be resilient: skip malformed entries
            continue

def _mirror_path_from_item(it: Dict[str, Any]) -> Optional[str]:
    r"""
    If 'doc_mirror' is missing, build one from src:
    C:\CFH\frontend\src\components\foo\Bar.tsx
      -> C:\CFH\docs\frontend\src\components\foo\Bar.md
    """
    src = it.get("src")
    if not src:
        return None
    p = Path(src)
    # map frontend root to docs\frontend
    try:
        rel = p.relative_to(FRONTEND_ROOT)
        # C:\CFH\docs\frontend\ + rel.with_suffix(".md")
        return str(DOCS_ROOT / ("frontend" / rel).with_suffix(".md"))
    except Exception:
        # generic fallback
        rel = p.name
        return str(DOCS_ROOT / (p.stem + ".md"))

def write_audit_csv(rows: List[Tuple[str, str, float, str, bool]], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["src", "dest", "confidence", "reason", "applied"])
        for r in rows:
            w.writerow(r)

def ensure_doc(doc_path: Path, src: Path, reason: str, confidence: float) -> bool:
    """
    Write a simple mirrored markdown if not present (or overwrite for demo).
    """
    try:
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        content = f"""# {src.name}

**Purpose**: Auto-generated mirror doc for `{src}`

- **Suggested location**: `{src.as_posix()}`
- **Confidence**: {confidence:.2f}
- **Reason**: {reason}

> Replace this stub with richer documentation as needed.
"""
        doc_path.write_text(content, encoding="utf-8")
        return True
    except Exception:
        return False

def apply_moves(sugs: Iterable[MoveSuggestion], threshold: float, do_execute: bool) -> Tuple[List[Tuple[str, str, float, str, bool]], int, int]:
    audit_rows: List[Tuple[str, str, float, str, bool]] = []
    moves_applied = 0
    docs_written  = 0

    for s in sugs:
        # Always write / refresh a doc mirror if we have a target path
        if s.doc_mirror:
            if ensure_doc(_normpath(s.doc_mirror), s.src, s.reason, s.confidence):
                docs_written += 1

        applied = False
        if s.confidence >= threshold and s.src != s.dest:
            if do_execute:
                try:
                    s.dest.parent.mkdir(parents=True, exist_ok=True)
                    # Move the file (overwrite if same name already exists)
                    if s.dest.exists():
                        s.dest.unlink()
                    s.src.replace(s.dest)
                    applied = True
                    moves_applied += 1
                except Exception:
                    applied = False
            else:
                # dry-run: not applying move, but will record as not applied
                applied = False

        audit_rows.append((
            str(s.src),
            str(s.dest),
            float(s.confidence),
            s.reason,
            bool(applied),
        ))

    return audit_rows, moves_applied, docs_written

def postprocess(artifact_path: str, threshold: float, execute: bool) -> Dict[str, Any]:
    ap = _normpath(artifact_path)
    data = load_artifact(ap)
    sugs = list(iter_suggestions(data))

    # Derive stable CSV name from artifact name (not timestamp now)
    out_csv = Path("reports") / f"routing_audit_{ap.stem}.csv"
    rows, moved, docs = apply_moves(sugs, threshold, execute)
    write_audit_csv(rows, out_csv)

    return {
        "ok": True,
        "artifact": str(ap),
        "audit_csv": str(out_csv).replace("/", "\\"),
        "rows": len(rows),
        "moves_applied": moved,
        "docs_written": docs,
        "threshold": threshold,
        "execute_moves": execute,
    }

def main() -> None:
    p = argparse.ArgumentParser(description="Post-process AI review artifacts: audit CSV, optional file moves, and docs mirroring.")
    p.add_argument("artifact", help="Path to reviews_*.json")
    p.add_argument("--threshold", type=float, default=0.85, help="Minimum confidence to apply a move (docs are written regardless)")
    p.add_argument("--execute", action="store_true", help="Actually move files (default is dry-run)")
    p.add_argument("--no-docs", action="store_true", help="(Reserved) – currently docs always write; flag kept for compatibility.")
    args = p.parse_args()

    res = postprocess(artifact_path=args.artifact, threshold=args.threshold, execute=args.execute)
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()
