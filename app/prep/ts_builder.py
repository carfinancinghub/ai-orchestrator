from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
import re

def build_ts_from_plans(md_paths: List[str], pruned_map: Optional[str], label: Optional[str]) -> Dict[str, Any]:
    """
    Minimal builder skeleton:
      - reads .plan.md (or per-file review .md)
      - writes .tsx stubs into src/_ai_out
      - returns {"written":[...], "errors":[...]}
    Replace with your richer builder later (consume resolved_deps, unified types, etc.)
    """
    out_root = Path("src") / "_ai_out"
    out_root.mkdir(parents=True, exist_ok=True)
    written: List[str] = []
    errors: List[str] = []

    for md in md_paths:
        try:
            p = Path(md)
            # normalize: foo.plan.md -> foo.plan.tsx   | review_*.md -> review_*.tsx
            name = re.sub(r"\.md$", ".tsx", p.name)
            outp = out_root / name
            banner = (
                f"/**\\n"
                f" * GENERATED from: {p.as_posix()}\\n"
                f" * date: {datetime.utcnow().isoformat()}Z\\n"
                f" */\\n\\n"
            )
            body = f"export const TODO_{re.sub(r'[^A-Za-z0-9_]', '_', p.stem)} = () => null;\\n"
            outp.write_text(banner + body, encoding="utf-8")
            written.append(outp.as_posix())
        except Exception as e:
            errors.append(f"{md}: {e!r}")

    return {"written": written, "errors": errors}
