from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()

class BuildTsRequest(BaseModel):
    md_paths: List[str] = Field(default_factory=list)
    out_dir: str = "src/_ai_out/redis_full"
    publishEvent: bool = True
    withMocks: bool = True
    fullClass: bool = True

def _safe_name(name: str) -> str:
    bad = " <>:\"/\\|?*'`"
    out = "".join(ch if ch not in bad else "_" for ch in name)
    # windows: also trim trailing dots/spaces
    return out.rstrip(". ")

def _stub_from_plan(md: str) -> Dict[str, str]:
    """
    Extremely naive: search for a component name and produce 1-2 files.
    This unblocks artifacts; you can replace with a stronger emitter later.
    """
    # find a component line like: component: EscrowQueueService
    comp = "Component"
    for line in md.splitlines():
        x = line.strip()
        if ":" in x and ("component" in x.lower() or x.startswith(comp)):
            _, val = x.split(":", 1)
            name = _safe_name(val.strip())
            if name:
                break
    else:
        name = "GeneratedComponent"

    files = {}
    files[f"{name}.ts"] = f"""// Auto-generated stub
export class {name} {{
  constructor() {{}}
  async connect() {{}}
  async disconnect() {{}}
}}
"""
    files[f"{name}.test.ts"] = f"""// Auto-generated placeholder tests for {name}
import {{ {name} }} from "./{name}";

test("{name} instantiation", () => {{
  const x = new {name}();
  expect(x).toBeTruthy();
}});
"""
    return files

@router.post("/build_ts")
def build_ts(req: BuildTsRequest) -> Dict[str, Any]:
    out_dir = Path(req.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    written: List[str] = []
    logs: List[str] = []

    for p in req.md_paths:
        path = Path(p)
        if not path.exists():
            logs.append(f"skip: missing {p}")
            continue
        try:
            md = path.read_text(encoding="utf-8")
        except Exception as e:
            logs.append(f"read_fail: {p} -> {e!r}")
            continue

        stub_map = _stub_from_plan(md)
        for rel, content in stub_map.items():
            target = out_dir / rel
            target.write_text(content, encoding="utf-8")
            written.append(str(target))

    return {
        "ok": True,
        "out_dir": str(out_dir),
        "written": written,
        "logs": logs,
    }