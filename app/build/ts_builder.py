from __future__ import annotations
from pathlib import Path
from typing import List, Dict
import json, os, shutil

OUTROOT = Path("reports/build")

def consume_md_and_map(md_paths: List[Path], pruned_map_csv: Path) -> Dict:
    # parse inputs (stub: record paths only)
    return {"md": [str(p) for p in md_paths], "pruned_map": str(pruned_map_csv)}

def emit_ts_module(module: str, plan: Dict) -> Path:
    out = OUTROOT / f"{module}-module"
    if out.exists():
        shutil.rmtree(out)
    (out / "src").mkdir(parents=True, exist_ok=True)
    # minimal shared barrel + test stub; builder AI will flesh out later
    (out / "src" / "index.ts").write_text('export * from "./shared";\n')
    (out / "src" / "shared.ts").write_text('export interface BidProps { amount: number; userId: string; }\n')
    (out / "src" / "shared.test.ts").write_text('import { describe, it, expect } from "vitest"; describe("shared", ()=>{ it("ok", ()=> expect(true).toBe(true)); });\n')
    (out / "plan.json").write_text(json.dumps(plan, indent=2))
    return out
