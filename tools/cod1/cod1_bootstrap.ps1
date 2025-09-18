# Cod1 Continuity Bootstrap (PowerShell) — paste-safe
$ErrorActionPreference = "Stop"

# 0) Configure paths/branch
$AIO = "C:\c\ai-orchestrator"        # <-- adjust for your machine
$BR  = "fix/sgman-full-ops"
$run = Get-Date -Format yyyyMMdd_HHmmss

# 1) Ensure repo + branch
if (-not (Test-Path $AIO)) { throw "AIO path not found: $AIO" }
Set-Location $AIO
if (-not (git rev-parse --git-dir 2>$null)) { throw "Not a git repo: $AIO" }

$cur = git rev-parse --abbrev-ref HEAD
if ($cur -ne $BR) { git checkout -B $BR | Out-Null }

# 2) Folders (idempotent)
$dirs = @(
  "artifacts/suggestions/$run",
  "artifacts/specs",
  "artifacts/generated",
  "artifacts/reviews/$run/verify",
  "reports/debug",
  "reports/gates",
  "logs"
)
$dirs | ForEach-Object {
  $p = Join-Path $AIO $_
  New-Item -ItemType Directory -Force -Path $p | Out-Null
}

# 3) Write app/cod1_continuity.py in safe chunks (no hanging here-strings)
$cod1 = Join-Path $AIO "app/cod1_continuity.py"
New-Item -ItemType Directory -Force -Path (Split-Path $cod1) | Out-Null

$P1 = @'
from __future__ import annotations
import os, json, re, subprocess, shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

ROOT   = Path(os.getenv("AIO_ROOT", Path(__file__).resolve().parents[1]))
REPORTS= ROOT/"reports"/"debug"
SUGG   = ROOT/"artifacts"/"suggestions"
SPECS  = ROOT/"artifacts"/"specs"
GEN    = ROOT/"artifacts"/"generated"
REV    = ROOT/"artifacts"/"reviews"
LOGS   = ROOT/"logs"

for p in [REPORTS, SUGG, SPECS, GEN, REV, LOGS]:
    p.mkdir(parents=True, exist_ok=True)

def ts_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def _safe_write(path: Path, content: str) -> Tuple[bool, Path]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup  = path.with_suffix(path.suffix + f".bak_{ts_run_id()}")
        shutil.copy2(path, backup)
        sibling = path.with_name(path.stem + f"__{ts_run_id()}" + path.suffix)
        sibling.write_text(content, encoding="utf-8")
        return False, sibling
    else:
        path.write_text(content, encoding="utf-8")
        return True, path
'@

$P2 = @'
def review_file(target: Path, run_id: Optional[str]=None, gh_repo: Optional[str]=None, gh_ref: str="main") -> Path:
    run_id = run_id or ts_run_id()
    target = target.resolve()
    base   = target.name
    out    = REPORTS / f"file_review_{base}_{run_id}.md"

    local_exists = target.exists()
    local_text   = target.read_text(encoding="utf-8", errors="replace") if local_exists else ""

    remote_text = None
    if gh_repo:
        try:
            proc = subprocess.run([
                "gh","api", f"/repos/{gh_repo}/contents/{str(target).split('CFH\\\\frontend\\\\')[-1].replace('\\\\','/')}",
                "-H","Accept: application/vnd.github.VERSION.raw",
                "-q","."
            ], capture_output=True, text=True)
            if proc.returncode == 0 and proc.stdout:
                remote_text = proc.stdout
        except Exception:
            remote_text = None

    needs_types = bool(re.search(r"\bPropTypes\b|//\s*TODO:.*types|any\b", local_text)) or (".jsx" in base.lower() or ".js" in base.lower())

    notes = []
    if ".jsx" in base.lower():
        notes.append("Convert to .tsx, add FC<Props> typing, children?: ReactNode")
    if "useState(" in local_text or "useEffect(" in local_text:
        notes.append("Add typed state/effect dependencies; prefer explicit types when crossing module boundaries")
    if "fetch(" in local_text or "axios" in local_text:
        notes.append("Type network responses; define DTOs and narrow to view models")
    if "default export" in local_text:
        notes.append("Prefer named exports for tree-shaking and clearer imports")

    remote_delta = None
    if remote_text is not None and local_text:
        remote_delta = "[remote content present — manual diff required]"

    md = [
        f"# File Review — {base}",
        f"Run ID: {run_id}",
        f"Local exists: {local_exists}",
        f"GitHub repo: {gh_repo or '-'} @ {gh_ref}",
        "",
        "## Summary",
        f"- Path: {target}",
        f"- Size: {len(local_text)} bytes",
        f"- Needs type work: {'yes' if needs_types else 'unknown'}",
        "",
        "## Notable Elements",
        "- Hooks used: `useState`, `useEffect` if present",
        "- Routing/lazy: check `React.lazy`/`Suspense`",
        "- Props flow: identify prop drilling vs context",
        "",
        "## Conversion Needs",
        *([f"- {n}" for n in notes] or ["- Inspect file to determine precise actions"]),
        "",
        "## Remote Check",
        remote_delta or "- Remote not fetched or no local content",
        "",
        "## Next Steps",
        "1) Suggest features (perform worth scoring)",
        "2) Generate spec MD",
        "3) Generate TS/TSX",
        "4) Re-review vs spec & suggestions"
    ]

    _safe_write(out, "\n".join(md))
    return out
'@

$P3 = @'
def suggest_features(target: Path, run_id: Optional[str]=None) -> Path:
    run_id = run_id or ts_run_id()
    base   = target.name
    out    = (SUGG / run_id / f"{base}.json")
    suggestions = [
        {"id":"lazy-load-notfound","title":"Lazy load NotFound page","worth_score":72, "rationale":"Saves JS on main route; improves TTUI"},
        {"id":"prop-types-to-ts","title":"Replace PropTypes with TS interfaces","worth_score":88, "rationale":"Eliminate runtime checks; shift to compile-time"},
        {"id":"strict-null","title":"Enable strict null checks in component state","worth_score":65, "rationale":"Avoid undefined paths in effects"}
    ]
    _safe_write(out, json.dumps(suggestions, indent=2))
    return out

def generate_spec_md(target: Path, suggestions_json: Path, run_id: Optional[str]=None) -> Path:
    run_id  = run_id or ts_run_id()
    base    = target.name
    name_wo = Path(base).stem
    out     = SPECS / f"{name_wo}_spec.md"
    sugg    = json.loads(Path(suggestions_json).read_text(encoding="utf-8"))
    bullets = "\n".join([f"- [{s['worth_score']:>3}] {s['title']} — {s['rationale']}" for s in sugg])

    md = f"""# Spec — {base}
Run ID: {run_id}

## Overview
- Preserve behavior; no breaking UI changes
- Add TS interfaces/types for props, state, and external data
- Introduce small perf wins that don't alter UX semantics

## Suggested Changes
{bullets}

## Generated Code Snippet (sketch)
```tsx
// Pseudocode scaffold — generator will replace
export interface Props {{}}
export function ComponentName(props: Props) {{
  return (<div />);
}}
```

## Review Criteria
- Types applied to public props and exported functions
- No `any` unless justified with inline comment and TODO
- Lazy-loading applied where high-worth suggestion indicates
- Lint passes; build passes
- Unit smoke test added if file is non-trivial
"""
    _safe_write(out, md)
    return out
'@

$P4 = @'
def generate_ts_file(target: Path, spec_md: Path, run_id: Optional[str]=None) -> Path:
    run_id  = run_id or ts_run_id()
    base    = target.name
    name_wo = Path(base).stem
    ext     = ".tsx" if base.lower().endswith(".jsx") else ".ts"
    out     = GEN / f"{name_wo}{ext}"
    code    = f"// Generated by Cod1 Continuity — {run_id}\n// Source: {target}\n\nexport const PLACEHOLDER = true;\n"
    _safe_write(out, code)
    return out

def review_generated_file(generated: Path, spec_md: Path, run_id: Optional[str]=None) -> Path:
    run_id   = run_id or ts_run_id()
    out      = (REV / run_id / "verify" / f"{generated.name}.json")
    gen_text = Path(generated).read_text(encoding="utf-8") if Path(generated).exists() else ""
    spec_txt = Path(spec_md).read_text(encoding="utf-8") if Path(spec_md).exists() else ""
    issues   = []
    if "PLACEHOLDER" in gen_text:
        issues.append("Generator placeholder present — needs real code generation")
    payload  = {"run_id": run_id, "file": str(generated), "spec": str(spec_md),
                "suggestions_applied": False if issues else True, "issues": issues}
    _safe_write(out, json.dumps(payload, indent=2))
    return out

def cod1_pipeline_for_file(target: Path, gh_repo: Optional[str]=None, run_id: Optional[str]=None) -> Dict[str, str]:
    run_id = run_id or ts_run_id()
    r = review_file(target, run_id=run_id, gh_repo=gh_repo)
    s = suggest_features(target, run_id=run_id)
    m = generate_spec_md(target, s, run_id=run_id)
    g = generate_ts_file(target, m, run_id=run_id)
    v = review_generated_file(g, m, run_id=run_id)
    return {"review": str(r), "suggestions": str(s), "spec": str(m), "generated": str(g), "verify": str(v), "run_id": run_id}
'@

$parts = @($P1, "", $P2, "", $P3, "", $P4)
Set-Content -Path $cod1 -Value ($parts -join "`n") -Encoding UTF8

# 4) Hook into ops.py (idempotent)
$ops = Join-Path $AIO "app/ops.py"
if (-not (Select-String -Path $ops -Pattern "Cod1 Continuity Hook \(import\)" -Quiet)) {
@'
# ==== Cod1 Continuity Hook (import) ====
try:
    from app.cod1_continuity import cod1_pipeline_for_file
except Exception as _e:
    cod1_pipeline_for_file = None  # fallback if module missing
# ==== Cod1 Continuity Hook - END ====
'@ | Add-Content -Path $ops -Encoding UTF8
}

if (-not (Select-String -Path $ops -Pattern "Cod1 Continuity Hook \(dispatcher\)" -Quiet)) {
@'
# ==== Cod1 Continuity Hook (dispatcher) ====
if "cod1" not in globals():
    def cod1(file_paths: list[str], gh_repo: str|None=None):
        results = []
        if "cod1_pipeline_for_file" not in globals() or cod1_pipeline_for_file is None:
            return results
        from pathlib import Path
        for fp in file_paths:
            try:
                res = cod1_pipeline_for_file(Path(fp), gh_repo=gh_repo)
                results.append(res)
            except Exception as e:
                results.append({"error": str(e), "file": fp})
        return results
# ==== Cod1 Continuity Hook (dispatcher) - END ====
'@ | Add-Content -Path $ops -Encoding UTF8
}

# 5) Commit + push
git add app/cod1_continuity.py app/ops.py
git commit -m "Cod1 Continuity: helper module + ops hook (no-overwrite guards)" 2>$null | Out-Null
git push -u origin $BR

# 6) Report stub
$rep = Join-Path $AIO ("reports/debug/cod1_report_{0}.md" -f (Get-Date -Format yyyyMMdd_HHmm))
@"
# Cod1 Report — $(Get-Date -Format s)
[Task 1] Review → Suggest → Spec → Generate → Verify
Status: ✅ Bootstrap complete
Run ID: $run
Outputs:
- suggestions: artifacts/suggestions/$run/
- specs:       artifacts/specs/
- generated:   artifacts/generated/
- reviews:     artifacts/reviews/$run/verify/
Notes: generator uses placeholder content for now.
"@ | Set-Content -Path $rep -Encoding UTF8

Write-Host "Bootstrap complete on branch $BR. Run id: $run"
