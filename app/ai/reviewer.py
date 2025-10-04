# app/ai/reviewer.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
import os
import re

# Domains we route into (extend freely)
DOMAINS = [
    "buyer", "seller", "lender", "mechanic", "admin", "auction", "escrow",
    "insurance", "judge", "hauler", "common", "internal", "finance",
    "analytics", "marketplace", "notifications", "onboarding", "support",
]

# Simple heuristics to suggest a domain; will be replaced by LLM later.
KEYWORD_TO_DOMAIN = [
    (re.compile(r"\bbuyer\b", re.I), "buyer"),
    (re.compile(r"\bseller\b", re.I), "seller"),
    (re.compile(r"\blender\b|\bloan\b", re.I), "lender"),
    (re.compile(r"\bmechanic\b|\binspection\b", re.I), "mechanic"),
    (re.compile(r"\badmin\b", re.I), "admin"),
    (re.compile(r"\bauction\b|\bbid\b", re.I), "auction"),
    (re.compile(r"\bescrow\b", re.I), "escrow"),
    (re.compile(r"\binsur", re.I), "insurance"),
    (re.compile(r"\bjudge\b|\barbitrator\b|\bdispute", re.I), "judge"),
    (re.compile(r"\bhauler\b|\btransport", re.I), "hauler"),
    (re.compile(r"\banalytics\b", re.I), "analytics"),
    (re.compile(r"\bmarketplace\b|\blisting\b", re.I), "marketplace"),
    (re.compile(r"\bnotifi|\bemail|\bsms", re.I), "notifications"),
    (re.compile(r"\bonboard", re.I), "onboarding"),
    (re.compile(r"\bsupport\b|\bticket\b", re.I), "support"),
]

def _guess_domain(text: str, fallback: str = "common") -> tuple[str, float, str]:
    for rx, dom in KEYWORD_TO_DOMAIN:
        if rx.search(text):
            return dom, 0.88, f"Matched keyword rule: {rx.pattern}"
    return fallback, 0.65, "Fallback to 'common' (no keyword match)"

def review_file(src_path: str, repo_root: str | None = None) -> Dict[str, Any]:
    """
    Returns a dict containing a top-of-file ROUTING JSON block and a short markdown.
    This is a rule-based stand-in. Later, plug your LLM call here and keep the same output shape.
    """
    p = Path(src_path)
    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        text = ""

    # Combine hints from path + content
    hint_blob = f"{p.as_posix()} :: {text[:2000]}"
    dest_domain, confidence, reason = _guess_domain(hint_blob)

    # Default frontend/docs roots (can be overridden via env)
    docs_root = os.getenv("DOCS_ROOT", r"C:\CFH\docs")
    if repo_root is None:
        repo_root = r"C:\CFH\frontend"

    # Destination suggestion for needsHome or unknown placement
    try:
        rel = str(Path(src_path).relative_to(repo_root)).replace("\\", "/")
    except Exception:
        rel = p.name

    # If the file is already under its domain, lower confidence
    already_domain = f"/{dest_domain}/" in ("/" + rel)
    effective_conf = confidence if not already_domain else 0.60
    dest_rel = re.sub(r"/needsHome/", f"/{dest_domain}/", rel)
    dest_abs = str(Path(repo_root, dest_rel))

    routing = {
        "suggested_moves": [
            {
                "src": str(p).replace("\\", "/"),
                "dest": dest_abs.replace("\\", "/"),
                "confidence": round(effective_conf, 2),
                "reason": reason,
            }
        ]
    }

    md = f"""# File Review: {p.name}

**Purpose (heuristic):** Suggest placement under **{dest_domain}**  
**Reason:** {reason}  
**Confidence:** {round(effective_conf, 2)}

## Snippet
```tsx
{text[:400]}
```"""

    return {
        "routing": routing,
        "markdown": md,
        "domains": DOMAINS,
        "docs_root": docs_root,
        "repo_root": repo_root,
    }
