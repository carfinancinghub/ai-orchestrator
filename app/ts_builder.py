# app/prep/ts_builder.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
import re
import inspect

def _simple_stub(md_paths: List[str]) -> Dict[str, Any]:
    out_root = Path("src") / "_ai_out"
    out_root.mkdir(parents=True, exist_ok=True)
    written: List[str] = []
    errors: List[str] = []
    for md in md_paths:
        try:
            p = Path(md)
            name = re.sub(r"\.md$", ".tsx", p.name)
            outp = out_root / name
            banner = (
                f"/**\n"
                f" * GENERATED (stub) from: {p.as_posix()}\n"
                f" * date: {datetime.utcnow().isoformat()}Z\n"
                f" */\n\n"
            )
            body = f"export const TODO_{re.sub(r'[^A-Za-z0-9_]', '_', p.stem)} = () => null;\n"
            outp.write_text(banner + body, encoding="utf-8")
            written.append(outp.as_posix())
        except Exception as e:
            errors.append(f"{md}: {e!r}")
    return {"written": written, "errors": errors}

def build_ts_from_plans(md_paths: List[str], pruned_map: Optional[str], label: Optional[str]) -> Dict[str, Any]:
    """
    Preferred: call legacy app.ts_builder.build_ts_from_plans(md_paths, out_dir, conf_gate).
    Fallback: simple stub that writes stubs to src/_ai_out.
    """
    # Try legacy builder if present
    try:
        import app.ts_builder as legacy  # type: ignore
        if hasattr(legacy, "build_ts_from_plans"):
            fn = legacy.build_ts_from_plans  # type: ignore[attr-defined]
            sig = inspect.signature(fn)
            params = list(sig.parameters.keys())
            # legacy signature we saw: (md_paths, out_dir, conf_gate=0.85)
            if len(params) >= 2 and params[0] == "md_paths":
                out_dir = Path("src") / "_ai_out"
                out_dir.mkdir(parents=True, exist_ok=True)
                try:
                    if len(params) >= 3:
                        res = fn(md_paths, out_dir, 0.85)  # type: ignore[call-arg]
                    else:
                        res = fn(md_paths, out_dir)        # type: ignore[call-arg]
                    if isinstance(res, list):
                        return {"written": [str(p) for p in res], "errors": []}
                    if isinstance(res, dict):
                        return {
                            "written": [str(p) for p in res.get("written", [])],
                            "errors": [str(e) for e in res.get("errors", [])],
                        }
                    return {"written": [str(res)], "errors": []}  # type: ignore[list-item]
                except Exception as e:
                    return {"written": [], "errors": [f"legacy_builder_error: {e!r}"]}
    except Exception:
        pass

    # Fallback stub
    return _simple_stub(md_paths)
