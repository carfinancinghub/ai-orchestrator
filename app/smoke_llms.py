# Path: app/smoke_llms.py  (UPDATED: deterministic sample + optional App.tsx checks)
from __future__ import annotations
import os
import json
from pathlib import Path
from typing import Dict

ART = Path("artifacts"); ART.mkdir(exist_ok=True)
SMOKE_DIR = ART / "smoke"; SMOKE_DIR.mkdir(parents=True, exist_ok=True)

def write_sample_add() -> Dict[str, str]:
    ts = "export function add(a: number, b: number): number { return a + b; }\n"
    test = (
        "import { add } from './add';\n"
        "describe('add', () => {\n"
        "  it('adds two numbers', () => { expect(add(2,3)).toBe(5); });\n"
        "});\n"
    )
    (SMOKE_DIR / "add.ts").write_text(ts, encoding="utf-8")
    (SMOKE_DIR / "add.test.ts").write_text(test, encoding="utf-8")
    return {"add.ts": ts, "add.test.ts": test}

def verify_expected(sample: Dict[str,str]) -> Dict[str, bool]:
    ok_ts = sample["add.ts"].strip() == "export function add(a: number, b: number): number { return a + b; }"
    ok_test = "expect(add(2,3)).toBe(5)" in sample["add.test.ts"]
    return {"add_ts_ok": ok_ts, "add_test_ok": ok_test}

def verify_app_tsx() -> Dict[str, str]:
    # Optional check: frontend/src/App.tsx (or APP_TSX_PATH env) if present
    app_path = os.getenv("APP_TSX_PATH") or "frontend/src/App.tsx"
    p = Path(app_path)
    if not p.exists():
        return {"status": "skipped", "reason": f"not found: {app_path}"}
    text = p.read_text(encoding="utf-8", errors="ignore")
    has_react_fc = "React.FC" in text
    has_at_import = any(line.strip().startswith("import ") and ("'@/" in line or '"@/' in line) for line in text.splitlines())
    has_any = " any" in text or ": any" in text
    status = "pass" if (has_react_fc and has_at_import and not has_any) else "fail"
    return {
        "status": status,
        "has_react_fc": str(has_react_fc),
        "has_at_import": str(has_at_import),
        "has_no_any": str(not has_any),
        "path": app_path,
    }

def main():
    sample = write_sample_add()
    checks = verify_expected(sample)
    app_check = verify_app_tsx()
    out = {"ok": all(checks.values()) and app_check.get("status","skipped") in ("pass","skipped"),
           "sample_checks": checks, "app_check": app_check,
           "paths": {"ts": str(SMOKE_DIR / "add.ts"), "test": str(SMOKE_DIR / "add.test.ts")}}
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
