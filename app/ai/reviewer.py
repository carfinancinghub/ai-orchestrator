# C:\c\ai-orchestrator\app\ai\reviewer.py
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


# Simple keyword → subfolder hints; add more as you learn the repo.
BUCKET_RULES: List[Tuple[str, str, float]] = [
    (r"\bbuyer\b|\bcheckout\b|\bbidder\b",           "buyer",        0.85),
    (r"\bseller\b|\blisting\b|\binventory\b",        "seller",       0.85),
    (r"\blender\b|\bloan\b|\bunderwrite|\bfico\b",   "lender",       0.85),
    (r"\bescrow\b|\bwallet\b|\bsettlement\b",        "escrow",       0.80),
    (r"\bauction\b|\blot\b|\breserve\b",             "auction",      0.80),
    (r"\bdisput(e|es)\b|\barbitrator\b|\bappeal\b",  "disputes",     0.78),
    (r"\bmechanic\b|\binspection\b|\brepair\b",      "mechanic",     0.80),
    (r"\binsur(ance|er)\b|\bcarrier\b|\bpolicy\b",   "insurance",    0.78),
    (r"\badmin\b|\btenant\b|\brole\b|\bpermission\b","admin",        0.75),
    (r"\bchat\b|\bmessage\b|\bthread\b",             "chat",         0.72),
    (r"\banalytic(s|s-)\b|\bmetric\b|\bdashboard\b", "analytics",    0.72),
    (r"\bcontract\b|\bagreement\b|\bsignature\b",    "contract",     0.72),
    (r"\bgamification\b|\bbadge\b|\blevel\b",        "gamification", 0.70),
    (r"\bcommon\b|\bshared\b|\butil(s|ity)\b",       "common",       0.65),
]

CODE_EXTS = {".ts", ".tsx", ".js", ".jsx"}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        try:
            return path.read_text(encoding="latin-1", errors="replace")
        except Exception:
            return ""


def heuristic_route(text: str, default_bucket: str | None = None) -> Tuple[str | None, float, str]:
    """
    Return (bucket, confidence, reason) based on simple keyword rules.
    If no rule matches, return (default_bucket, 0.5, reason) if provided, else (None, 0.0, reason).
    """
    lower = text.lower()
    for pattern, bucket, score in BUCKET_RULES:
        if re.search(pattern, lower):
            return bucket, score, f"Matched pattern '{pattern}' → '{bucket}'"
    if default_bucket:
        return default_bucket, 0.50, f"No strong match; defaulting to '{default_bucket}'"
    return None, 0.0, "No routing keyword match"


def build_markdown_summary(src: Path, text: str, dest_subdir: str | None, confidence: float, reason: str) -> str:
    # very lightweight “doc” — replace with richer prompt later
    head = src.name
    ext  = src.suffix
    lines = text.splitlines()
    preview = "\n".join(lines[:20])  # first 20 lines as context
    md = []
    md.append(f"# {head}")
    md.append("")
    md.append(f"**Detected Type:** `{ext}`  |  **Suggested Dest:** `{dest_subdir or 'unknown'}`  |  **Confidence:** `{confidence:.2f}`")
    md.append("")
    md.append("## Purpose (heuristic)")
    md.append(f"- " + (reason or "No reason"))
    md.append("")
    md.append("## Code Preview")
    md.append("```")
    md.append(preview)
    md.append("```")
    md.append("")
    md.append("> This summary is heuristic-only. Replace with LLM-backed analysis later.")
    return "\n".join(md)


def review_file(src_path: str, repo_root: str | None = None) -> Dict[str, Any]:
    """
    Produce:
      {
        "routing": {
            "suggested_moves": [
               {"src": "...", "dest": "...", "confidence": 0.87, "reason": "..."}
            ]
        },
        "markdown": "..."
      }
    """
    p = Path(src_path)
    text = _read_text(p)
    if not text:
        return {"routing": {"suggested_moves": []}, "markdown": ""}

    # Heuristic routing
    bucket, score, reason = heuristic_route(text)

    # Build a destination path inside components if we’re in a frontend repo
    # FRONTEND_ROOT env var can override (e.g., C:\CFH\frontend)
    repo_root = repo_root or os.getenv("FRONTEND_ROOT", r"C:\CFH\frontend")
    dest = None
    if bucket:
        try:
            # if file is within frontend/src/components, mirror subpath; otherwise place under bucket directly
            components = Path(repo_root) / "src" / "components"
            suffix_subpath = p.name
            dest_dir = components / bucket
            dest = str((dest_dir / suffix_subpath).resolve())
        except Exception:
            dest = None

    markdown = build_markdown_summary(p, text, bucket, score, reason)

    move = {
        "src": str(p),
        "dest": dest or "",
        "confidence": float(score),
        "reason": reason,
    }

    return {
        "routing": {"suggested_moves": [move]},
        "markdown": markdown,
    }
