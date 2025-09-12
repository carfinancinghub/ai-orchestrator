# Path: app/services/validation/validate.py
from __future__ import annotations
import re
import subprocess
from typing import Iterable, Optional, Dict, Any

def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        return p.returncode, p.stdout
    except Exception as e:
        return 127, f"{type(e).__name__}: {e}"

def _parse_jest_coverage(output: str) -> Optional[float]:
    # Try to parse TOTAL line percentage
    m = re.search(r"TOTAL\s+\d+\s+\d+\s+\d+\s+\d+\s+(\d+(?:\.\d+)?)\s*%", output)
    if m:
        return float(m.group(1))
    # Fallback: any "All files" summary
    m = re.search(r"All files.*?(\d+(?:\.\d+)?)\s*%\s*$", output, re.S | re.M)
    return float(m.group(1)) if m else None

def run_full_validation(
    paths: Optional[Iterable[str]] = None,
    test_path: Optional[str] = None,
    coverage_threshold: float = 70.0,
) -> Dict[str, Any]:
    """
    Targeted validation:
      - tsc --noEmit {path} for each path (best-effort single-file typecheck)
      - jest {test_path} --coverage (log coverage %)
      - eslint {path} --fix for each path
    If required tool isn't available, record reason but do NOT hard-fail.
    On failure, attempt 'ts-migrate migrate .' as a best-effort assist.
    """
    reasons = []
    ok = True

    # tsc per file
    if paths:
        for p in paths:
            rc, out = _run(["npx", "tsc", "--noEmit", p])
            if rc != 0 and "not found" not in out.lower():
                ok = False
                reasons.append({"tool": "tsc", "path": p, "output": out})

    # jest (single test target if provided)
    cov_pct = None
    if test_path:
        rc, out = _run(["npx", "jest", test_path, "--coverage"])
        if "not found" not in out.lower():
            cov_pct = _parse_jest_coverage(out)
            if rc != 0 or (cov_pct is not None and cov_pct < coverage_threshold):
                ok = False
                reasons.append({"tool": "jest", "path": test_path, "coverage": cov_pct, "output": out})
        else:
            reasons.append({"tool": "jest", "path": test_path, "output": out})

    # eslint per file
    if paths:
        for p in paths:
            rc, out = _run(["npx", "eslint", p, "--ext", ".ts,.tsx", "--fix"])
            if rc != 0 and "not found" not in out.lower():
                ok = False
                reasons.append({"tool": "eslint", "path": p, "output": out})

    # Fallback assist on failures
    if not ok:
        _run(["npx", "ts-migrate", "migrate", "."])

    return {"ok": ok, "reasons": reasons, "coverage": cov_pct}
