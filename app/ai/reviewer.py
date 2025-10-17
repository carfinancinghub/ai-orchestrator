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

# ---------------------------------------------------------------------------
# NEW: batch generation + builder interfaces used by routes.py
# ---------------------------------------------------------------------------
import json
from datetime import datetime

def _safe_name(s: str) -> str:
    return re.sub(r"[^\w\.-]+", "_", s).strip("_") or "file"

def _repo_rel(p: Path, base: Path | None = None) -> str:
    base = base or Path.cwd()
    try:
        return p.resolve().relative_to(base.resolve()).as_posix()
    except Exception:
        return p.as_posix().replace("\\", "/")

def _ensure_dir(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)

def _infer_dependencies(text: str) -> list[str]:
    # VERY lightweight heuristic—extend over time
    deps: list[str] = []
    low = text.lower()
    if "auction" in low or "bid" in low:
        deps.append("@services/auctionBids.ts")
    if "escrow" in low or "payment" in low:
        deps.append("C:/CFH/backend/routes/escrow/payments.js")
    if "loan" in low or "approval" in low:
        deps.append("@services/loanAiApproval.ts")
    # keep unique, preserve order
    out = []
    for d in deps:
        if d not in out:
            out.append(d)
    return out

def _tiers_block(src: Path, text: str, tier: str, dest_path: str | None, deps: list[str]) -> str:
    """
    Emit the exact structure SG Man asked for:
      - .md starts with full content/functions summary (we provide heuristics)
      - then Free / Premium / Wow++ sections
      - include a JSON block with 'routing' and 'dependencies'
    """
    # tiny "summary" using the earlier helpers you already have
    bucket, score, reason = heuristic_route(text)
    summary = build_markdown_summary(src, text, bucket, score, reason)

    routing = {
        "src": src.as_posix(),
        "dest": dest_path or "",
        "tier": tier,
        "confidence": float(score),
        "bucket": bucket or "",
        "reason": reason,
    }
    # JSON fenced block (exact keys)
    routing_json = json.dumps({"routing": routing, "dependencies": deps}, ensure_ascii=False, indent=2)

    # Three tiers as requested
    tiers = [
        "## Tiers",
        "",
        "### Free Tier",
        "- Basic scan: generic domain notes; **no** CFH types, **no** `@` aliases, **no** ecosystem pointers.",
        "",
        "### Premium Tier",
        "- CFH types/interfaces (`@models/Vehicle`, prop validation, interfaces).",
        "",
        "### Wow++ Tier",
        "- Advanced TS (async flows, error boundaries), **monetization sketch** (e.g., escrow fee calc for Phase 1).",
        "",
        "```json",
        routing_json,
        "```",
        "",
    ]

    return "\n".join([summary, ""] + tiers)

def review_batch(paths: list[str], tier: str, label: str | None, reports_dir: Path) -> dict:
    """
    Writes:
      - reports/<label>/batch_review_<stamp>.md
      - reports/<label>/mds/<safe>_review.md  (per file)
    Returns:
      {
        "per_file_mds": [...],
        "batch_md": "reports/<label>/batch_review_*.md",
        "dependencies": { "<repo-rel>": [ ... ] }
      }
    """
base = Path(reports_dir or "reports")
label = label or "wave"

# avoid double label, e.g., "reports\wave-mdfirst\wave-mdfirst"
out_dir = base if base.name == label else (base / label)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mds_dir = out_dir / "mds"
    _ensure_dir(mds_dir)

    per_file_mds: list[str] = []
    deps_map: dict[str, list[str]] = {}

    # Build batch body
    batch_lines: list[str] = []
    batch_lines.append(f"# Batch Review — {tier}  ({stamp})")
    batch_lines.append("")
    batch_lines.append(f"_Label:_ `{label}`  •  _Count:_ `{len(paths)}`")
    batch_lines.append("")

    for p_str in paths:
        p = Path(p_str)
        text = _read_text(p)
        rel = _repo_rel(p)

        bucket, score, reason = heuristic_route(text)
        # Suggested dest mirrors your review_file logic
        repo_root = os.getenv("FRONTEND_ROOT", r"C:\CFH\frontend")
        dest = None
        if bucket:
            try:
                components = Path(repo_root) / "src" / "components"
                dest = str((components / bucket / p.name).resolve())
            except Exception:
                dest = None

        deps = _infer_dependencies(text)
        deps_map[rel] = deps

        # Per-file .md
        md_body = _tiers_block(p, text, tier=tier, dest_path=dest, deps=deps)
        safe = _safe_name(rel)
        md_path = mds_dir / f"{safe}_review.md"
        _ensure_dir(md_path.parent)
        md_path.write_text(md_body, encoding="utf-8")
        per_file_mds.append(md_path.as_posix())

        # Batch rollup section
        batch_lines.append(f"### File: `{rel}`")
        batch_lines.append("")
        batch_lines.append(f"- Suggested bucket: `{bucket or 'unknown'}`  •  Confidence: `{score:.2f}`")
        batch_lines.append(f"- Proposed dest: `{dest or ''}`")
        if deps:
            batch_lines.append(f"- Dependencies: {', '.join(f'`{d}`' for d in deps)}")
        else:
            batch_lines.append("- Dependencies: _none inferred_")
        batch_lines.append("")

    batch_md = out_dir / f"batch_review_{stamp}.md"
    batch_md.write_text("\n".join(batch_lines) + "\n", encoding="utf-8")

    return {
        "per_file_mds": per_file_mds,
        "batch_md": batch_md.as_posix(),
        "dependencies": deps_map,
    }

# --- Build from .md to .tsx --------------------------------------------------

_JSON_FENCE_RE = re.compile(
    r"```json\s*(?P<json>\{.*?\})\s*```",
    re.IGNORECASE | re.DOTALL,
)

def _parse_routing_block(md_text: str) -> tuple[dict, list[str]]:
    """
    Find the first ```json { ... } ``` block and return (routing, dependencies)
    """
    m = _JSON_FENCE_RE.search(md_text)
    if not m:
        return {}, []
    try:
        obj = json.loads(m.group("json"))
    except Exception:
        return {}, []
    routing = obj.get("routing", {}) if isinstance(obj, dict) else {}
    deps = obj.get("dependencies", []) if isinstance(obj, dict) else []
    if not isinstance(deps, list):
        deps = []
    return routing, deps

def build_ts_from_md(md_path: str, apply_moves: bool = True) -> dict:
    """
    Read a per-file .md, extract routing + dependencies JSON, and write a .tsx stub
    at the routing.dest (if provided). Returns: {"written": [ ... ]}.
    """
    md_file = Path(md_path)
    if not md_file.exists():
        return {"written": [], "error": f"md_not_found:{md_path}"}

    text = _read_text(md_file)
    routing, deps = _parse_routing_block(text)

    dest = routing.get("dest") if isinstance(routing, dict) else None
    if not dest:
        # Try to reconstruct from bucket + original filename if present
        bucket = routing.get("bucket") if isinstance(routing, dict) else None
        src = routing.get("src") if isinstance(routing, dict) else None
        repo_root = os.getenv("FRONTEND_ROOT", r"C:\CFH\frontend")
        if bucket and src:
            try:
                dest = str((Path(repo_root) / "src" / "components" / bucket / Path(src).name).resolve())
            except Exception:
                dest = None

    if not dest:
        # Cannot route—return without writing
        return {"written": [], "error": "no_dest_in_routing"}

    out_path = Path(dest)
    _ensure_dir(out_path.parent)

    # Create a tiny TSX component (Wow++ placeholder)
    comp_name = _safe_name(out_path.stem).title().replace("_", "")
    deps_comment = "\n".join([f"// dep: {d}" for d in deps]) if deps else "// dep: (none)"
    content = f"""import React from "react";

/**
 * Auto-generated Wow++ sketch
 * Source MD: {md_file.name}
 * {deps_comment}
 */
export default function {comp_name}(): JSX.Element {{
  // TODO: implement monetization logic (e.g., escrow fee calc Phase 1)
  // TODO: wire CFH types/interfaces and validation
  return (
    <div data-component="{comp_name}">
      <h3>{comp_name}</h3>
      <p>Generated from reviewer Wow++ sketch. Replace with real implementation.</p>
    </div>
  );
}}
"""
    if apply_moves:
        out_path.write_text(content, encoding="utf-8")
        return {"written": [out_path.as_posix()]}
    else:
        # dry run of builder—no write
        return {"written": []}

