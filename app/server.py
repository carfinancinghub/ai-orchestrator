from __future__ import annotations

import os
import json
import time
import re
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field

import httpx
from openai import AsyncOpenAI

# ── Env / App ──────────────────────────────────────────────────────────────────
load_dotenv()

app = FastAPI(title="CFH AI Orchestrator", version="0.5.0")

ALLOWED_ORIGINS = [
    os.getenv("VITE_ORIGIN", "http://127.0.0.1:8020"),
    "http://localhost:8020",
    "http://127.0.0.1:8021",  # self
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Provider env
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

XAI_KEY = os.getenv("XAI_GROK_API_KEY") or os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY")
XAI_BASE = os.getenv("GROK_BASE_URL") or os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")
XAI_MODEL = os.getenv("GROK_MODEL", "grok-2-latest")

GOOGLE_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
GEMINI_BASE = os.getenv("GEMINI_BASE", "https://generativelanguage.googleapis.com/v1beta")
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-flash-latest")

PROVIDER_ORDER = [p.strip().lower() for p in (os.getenv("PROVIDER_ORDER") or "google,openai,grok").split(",") if p.strip()]
RETRY_MAX = int(os.getenv("RETRY_MAX", "3"))
RETRY_BASE_DELAY = float(os.getenv("RETRY_BASE_DELAY", "1.2"))

# Clients (created only if keys exist)
openai_client: Optional[AsyncOpenAI] = AsyncOpenAI(api_key=OPENAI_KEY, base_url=OPENAI_BASE) if OPENAI_KEY else None
xai_client: Optional[AsyncOpenAI] = AsyncOpenAI(api_key=XAI_KEY, base_url=XAI_BASE) if XAI_KEY else None

# ── Secret Redaction (logs & error text) ───────────────────────────────────────
_REDACT_PATTERNS = [
    (re.compile(r'(?:\?|&)(?:key|api_key)=([^&\s]+)', re.I), r'\g<0>[REDACTED]'),
    (re.compile(r'Authorization:\s*Bearer\s+[A-Za-z0-9._-]+', re.I), 'Authorization: Bearer [REDACTED]'),
    (re.compile(r'sk-[A-Za-z0-9]{20,}', re.I), 'sk-[REDACTED]'),             # OpenAI-like
    (re.compile(r'AIza[0-9A-Za-z\-_]{20,}', re.I), 'AIza[REDACTED]'),        # Google-like
    (re.compile(r'(?<=XAI_API_KEY=)[^\s]+', re.I), '[REDACTED]'),
]

def redact_secret(s: str) -> str:
    out = s
    for pat, repl in _REDACT_PATTERNS:
        out = pat.sub(repl, out)
    return out

class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_secret(record.msg)
        if record.args:
            try:
                new_args = []
                for a in record.args:
                    new_args.append(redact_secret(a) if isinstance(a, str) else a)
                record.args = tuple(new_args)
            except Exception:
                pass
        return True

logging.getLogger("uvicorn.error").addFilter(RedactFilter())
logging.getLogger("uvicorn.access").addFilter(RedactFilter())
logging.getLogger("httpx").addFilter(RedactFilter())

# ── Schemas ───────────────────────────────────────────────────────────────────
class ConvertRequest(BaseModel):
    file_path: str = Field(..., description="Path to a .js or .jsx file")
    provider: Optional[str] = Field(None, description="openai | grok | google | anthropic | auto/None for fallback")
    model: Optional[str] = Field(None, description="Provider-specific model or auto")

class ConvertResponse(BaseModel):
    saved_to: str
    bytes: int

class ConvertTreeRequest(BaseModel):
    root: str = Field(default="src")
    provider: Optional[str] = Field(default=None, description="openai | grok | google | anthropic | auto/None for fallback")
    model: Optional[str] = Field(default=None)
    limit: Optional[int] = Field(default=None, description="Optional max files to convert this run")
    dry_run: bool = Field(default=False, description="If true, do not write files; just preview")

class ConvertTreeResponse(BaseModel):
    ok: bool
    provider: Optional[str]
    model: Optional[str]
    converted: list[str]
    skipped: list[str]
    dry_run: bool
    metrics: Dict[str, Any]

# ── Utils: discovery & helpers ────────────────────────────────────────────────
EXCLUDE_DIRS = {
    "node_modules", ".venv", "venv", "dist", "build", ".git", "__pycache__", ".next",
    "coverage", "out", "release", "tmp", "temp", "__mocks__", "storybook", "stories", "tests"
}
EXCLUDE_SUBSTR = (".test.", ".spec.", "stories", "storybook")

def _is_excluded(p: Path) -> bool:
    parts = {seg.lower() for seg in p.parts}
    if any(d in parts for d in EXCLUDE_DIRS):
        return True
    sp = str(p).lower()
    if any(tok in sp for tok in EXCLUDE_SUBSTR):
        return True
    return False

def find_js_targets(root: Path) -> list[Path]:
    targets: list[Path] = []
    if not root.exists():
        return targets
    for p in root.rglob("*"):
        if p.is_dir():
            continue
        if _is_excluded(p):
            continue
        ext = p.suffix.lower()
        if ext not in (".js", ".jsx"):
            continue
        sibling_ts = p.with_suffix(".ts" if ext == ".js" else ".tsx")
        if sibling_ts.exists():
            continue
        targets.append(p)
    return targets

def _ts_path_for(js_path: Path) -> Path:
    return js_path.with_suffix(".ts" if js_path.suffix.lower() == ".js" else ".tsx")

def _offline_write(js_path: Path, js_code: str, provider_note: str = "offline"):
    ts_path = _ts_path_for(js_path)
    banner = f"// @ai-generated (fallback; provider={provider_note})\n"
    ts_path.write_text(banner + js_code, encoding="utf-8")
    return ts_path

def _build_prompt(js_code: str) -> str:
    return (
        "Convert this JavaScript to idiomatic TypeScript (or TSX if JSX), "
        "add minimal explicit types, preserve exports/ESM shape, and avoid runtime changes.\n\n"
        "```javascript\n"
        f"{js_code}\n"
        "```"
    )

# ── Provider Calls (sanitized errors) ─────────────────────────────────────────
async def _call_openai(prompt: str, model: Optional[str]) -> str:
    if not openai_client:
        raise RuntimeError("OPENAI_API_KEY not configured")
    m = model or OPENAI_MODEL
    resp = await openai_client.chat.completions.create(
        model=m,
        messages=[
            {"role": "system", "content": "You are a senior TypeScript migration assistant."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content or ""

async def _call_grok(prompt: str, model: Optional[str]) -> str:
    if not xai_client:
        raise RuntimeError("GROK/XAI key not configured")
    m = model or XAI_MODEL
    resp = await xai_client.chat.completions.create(
        model=m,
        messages=[
            {"role": "system", "content": "You are a senior TypeScript migration assistant."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content or ""

async def _call_gemini(prompt: str, model: Optional[str]) -> str:
    if not GOOGLE_KEY:
        raise RuntimeError("GOOGLE_API_KEY/GEMINI_API_KEY not configured")
    m = model or GOOGLE_MODEL
    url = f"{GEMINI_BASE}/models/{m}:generateContent?key={GOOGLE_KEY}"

    body = {
        "contents": [{
            "role": "user",
            "parts": [{"text": "You are a senior TypeScript migration assistant.\n\n" + prompt}]
        }]
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, json=body)

    if r.status_code == 429:
        raise HTTPException(429, "Google quota/429")
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f"Google HTTP {r.status_code}")

    data = r.json()
    try:
        if data.get("candidates") and data["candidates"][0].get("content", {}).get("parts"):
            return data["candidates"][0]["content"]["parts"][0]["text"]
        return f"// gemini response empty or blocked. Raw: {json.dumps(data)}"
    except Exception:
        return f"// gemini response parse error. Raw: {json.dumps(data)}"

async def _convert_with_provider_js_to_ts(src_path: Path, provider: Optional[str], model: Optional[str]) -> str:
    """
    Convert JS/JSX → TS/TSX using a specific provider, or fallback chain when provider is None/'auto'.
    Returns TS/TSX code string (without banner). If keys are missing, returns original JS as no-op.
    """
    js_code = src_path.read_text(encoding="utf-8")
    prompt = _build_prompt(js_code)

    if provider and provider != "auto":
        p = provider.lower()
        try:
            if p == "openai":
                return await _call_openai(prompt, model)
            if p == "grok":
                return await _call_grok(prompt, model)
            if p == "google":
                return await _call_gemini(prompt, model)
        except HTTPException as he:
            raise he
        except Exception as e:
            raise RuntimeError(redact_secret(str(e)))
        return js_code

    last_err: Optional[Exception] = None
    for p in PROVIDER_ORDER:
        try:
            if p == "google":
                return await _call_gemini(prompt, model)
            if p == "openai":
                return await _call_openai(prompt, model)
            if p == "grok":
                return await _call_grok(prompt, model)
        except HTTPException as he:
            last_err = he
        except Exception as e:
            last_err = e
    if last_err:
        raise RuntimeError(redact_secret(str(last_err)))
    return js_code

# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/_health")
async def health():
    return {"ok": True}

@app.get("/orchestrator/status")
async def status():
    return {"ok": True, "service": "orchestrator"}

@app.get("/providers/list")
async def providers_list():
    return {
        "openai": bool(OPENAI_KEY),
        "grok": bool(XAI_KEY),
        "google": bool(GOOGLE_KEY),
        "anthropic": False,  # reserved
        "order": PROVIDER_ORDER,
    }

# Self-test (sanitized)
@app.get("/providers/selftest")
async def providers_selftest():
    msg = "hello-orchestrator"
    out: Dict[str, str] = {}

    async def grok():
        try:
            resp = await _call_grok(msg, None)
            return f"MODEL: {XAI_MODEL} | RESPONSE: {resp}"
        except HTTPException as he:
            return f"ERROR: Grok {he.detail}"
        except Exception as e:
            return f"ERROR: {redact_secret(str(e))}"

    async def google():
        try:
            resp = await _call_gemini(msg, None)
            return f"MODEL: {GOOGLE_MODEL} | RESPONSE: {resp}"
        except HTTPException as he:
            return f"ERROR: Google {he.detail}"
        except Exception as e:
            return f"ERROR: {redact_secret(str(e))}"

    async def openai():
        try:
            resp = await _call_openai(msg, None)
            return f"MODEL: {OPENAI_MODEL} | RESPONSE: {resp}"
        except HTTPException as he:
            return f"ERROR: OpenAI {he.detail}"
        except Exception as e:
            return f"ERROR: {redact_secret(str(e))}"

    for p in PROVIDER_ORDER:
        if p == "google":
            out["google"] = (await google())[:200]
        elif p == "openai":
            out["openai"] = (await openai())[:200]
        elif p == "grok":
            out["grok"] = (await grok())[:200]
        else:
            out[p] = "skipped"
    if "grok" not in out and XAI_KEY:
        out["grok"] = (await grok())[:200]
    if "google" not in out and GOOGLE_KEY:
        out["google"] = (await google())[:200]
    if "openai" not in out and OPENAI_KEY:
        out["openai"] = (await openai())[:200]
    return out

# Live route index (for quick parity checks)
@app.get("/_meta/routes")
def list_routes():
    routes = []
    for r in app.routes:
        if isinstance(r, APIRoute):
            methods = sorted(list(r.methods - {"HEAD", "OPTIONS"}))
            routes.append({"path": r.path, "methods": methods, "name": r.name})
    return {"count": len(routes), "routes": routes}

# Scanner
@app.get("/orchestrator/scan")
async def scan_files(root: Optional[str] = None):
    base = Path(root or "src")
    if not base.exists():
        return {"files": [], "count": 0}
    files: List[str] = [str(p) for p in find_js_targets(base)]
    return {"files": files, "count": len(files)}

# Convert: single
@app.post("/convert/file", response_model=ConvertResponse)
async def convert_file(req: ConvertRequest):
    path = Path(req.file_path)
    if not path.exists() or path.suffix.lower() not in (".js", ".jsx"):
        raise HTTPException(status_code=404, detail="File not found or not JS/JSX")

    provider = (req.provider or os.getenv("LLM_PROVIDER") or "auto").lower()
    model = req.model or os.getenv("LLM_MODEL")
    try:
        ts_code = await _convert_with_provider_js_to_ts(path, provider, model)
        ts_path = _ts_path_for(path)
        banner = f"// @ai-generated via ai-orchestrator (provider={provider})\n"
        ts_path.write_text(banner + (ts_code or ""), encoding="utf-8")
        return ConvertResponse(saved_to=str(ts_path), bytes=ts_path.stat().st_size)
    except Exception:
        ts_path = _offline_write(path, path.read_text(encoding="utf-8"), provider_note=f"{provider}-error")
        return ConvertResponse(saved_to=str(ts_path), bytes=ts_path.stat().st_size)

# Convert: tree
@app.post("/convert/tree", response_model=ConvertTreeResponse)
async def convert_tree(req: ConvertTreeRequest):
    started = time.time()
    root = Path(req.root)
    targets = find_js_targets(root)
    if req.limit:
        targets = targets[: req.limit]

    converted: list[str] = []
    skipped: list[str] = []
    banner = "// @ai-generated via ai-orchestrator\n"

    provider = (req.provider or "auto").lower()
    model = req.model

    for p in targets:
        try:
            ts_code = await _convert_with_provider_js_to_ts(p, provider, model)
            if req.dry_run:
                skipped.append(str(p))
                continue
            out_path = _ts_path_for(p)
            out_path.write_text(banner + ts_code, encoding="utf-8")
            converted.append(str(out_path))
        except Exception as e:
            skipped.append(f"{p} :: {redact_secret(str(e))}")

    metrics = {
        "files_considered": len(targets),
        "converted_count": len(converted),
        "skipped_count": len(skipped),
        "elapsed_sec": round(time.time() - started, 3),
        "provider": provider,
        "model": model,
    }
    return ConvertTreeResponse(
        ok=True,
        provider=provider,
        model=model,
        converted=converted,
        skipped=skipped,
        dry_run=req.dry_run,
        metrics=metrics,
    )

# ── 3-Tier review: suggestions ────────────────────────────────────────────────
TIER_KEYS = ("free", "premium", "wow_plus")

def _dedupe_by_path_and_size(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out  = []
    for i in items:
        p = str(i.get("path","")).strip()
        s = int(i.get("size", -1))
        key = (p.lower(), s)
        if key in seen:
            continue
        seen.add(key)
        out.append({"path": p, "size": s})
    return out

def _classify_tiers(file_path: str) -> Dict[str, List[str]]:
    tiers = { "free": [], "premium": [], "wow_plus": [] }
    tiers["free"] += [
        "add explicit interfaces/types, no 'any'",
        "basic runtime guards for nullable/undefined props",
        "a11y: aria-attributes on interactive elements",
        "docs: add module header + usage notes"
    ]
    if re.search(r"(components|pages|routes|views)", file_path.replace("\\","/"), re.I):
        tiers["premium"] += [
            "memoization where safe (React.memo / useMemo)",
            "lightweight logging (console or tiny wrapper)",
            "extract constants/enums; remove magic strings",
            "i18n-ready: wrap user-facing text"
        ]
        tiers["wow_plus"] += [
            "instrumentation hooks for AI hints on empty/error states",
            "structured telemetry event (ready for RUM/OTel)"
        ]
    else:
        tiers["premium"] += [
            "avoid repeated fs/net calls; cache hot paths",
            "centralize error shapes; add Result<T,E> returns"
        ]
        tiers["wow_plus"] += [
            "AI validation step: pre-commit check describing public API deltas",
            "predictive prefetch for dependent resources (feature-flagged)"
        ]
    return tiers

def _render_markdown(date_utc: str, files: List[Dict[str, Any]], md_spec: str, alloc: Dict[str, int]) -> str:
    lines = []
    lines.append(f"# CFH Review & Suggestions ({date_utc}Z)")
    lines.append("")
    lines.append("## Provider Allocation (Tier 2)")
    lines.append("")
    lines.append(f"- Gemini (discover): {alloc.get('gemini',0)} files")
    lines.append(f"- OpenAI (gen): {alloc.get('openai',0)} files")
    lines.append(f"- Grok (fallback): {alloc.get('grok',0)} files")
    lines.append("")
    lines.append("## Spec Input (from ai_review_*.md)")
    lines.append("")
    lines.append("```md")
    lines.append(md_spec.strip())
    lines.append("```")
    lines.append("")
    lines.append("## File Suggestions (3-tier)")
    lines.append("")
    for f in files:
        tiers = _classify_tiers(f["path"])
        lines.append(f"### {f['path']}  _(size: {f['size']})_")
        for tier in TIER_KEYS:
            title = "WOW++" if tier == "wow_plus" else tier.capitalize()
            lines.append(f"**{title}**")
            for bullet in tiers[tier]:
                lines.append(f"- {bullet}")
            lines.append("")
    return "\n".join(lines)

@app.post("/review/stitch-and-rank")
async def review_stitch_and_rank(payload: Dict[str, Any]):
    ts_files = payload.get("ts_files") or []
    md_spec  = str(payload.get("md_spec") or "").strip()
    alloc    = payload.get("alloc")
    files    = _dedupe_by_path_and_size(ts_files)

    if not isinstance(alloc, dict):
        n = max(1, len(files))
        alloc = {
            "gemini": max(0, int(round(n*0.30))),
            "openai": max(0, int(round(n*0.50))),
            "grok":   max(0, n - int(round(n*0.30)) - int(round(n*0.50))),
        }

    out_dir = Path("reports") / "suggestions"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    md_path = out_dir / f"suggestions_{ts}.md"

    body = _render_markdown(time.strftime("%Y-%m-%dT%H:%M:%S"), files, md_spec, alloc)
    md_path.write_text(body, encoding="utf-8")

    return {
        "ok": True,
        "count": len(files),
        "alloc": alloc,
        "output_md": str(md_path)
    }

# ── Validation that persists artifacts ────────────────────────────────────────
@app.post("/review/validate")
async def review_validate(suggestions_md_path: str):
    path = Path(suggestions_md_path)
    if not path.exists():
        raise HTTPException(404, "Suggestions MD not found")

    md_content = path.read_text(encoding="utf-8")
    # Look for absolute/relative TS paths after markdown headings
    # (Keep simple: users often paste "### C:\...\Some.tsx  _(size: N)_")
    found = re.findall(r"^###\s+([^\n]+?\.(?:ts|tsx))\b", md_content, flags=re.MULTILINE)

    results = {"pass": 0, "fail": 0, "details": []}
    for pth in found:
        pth = pth.strip()
        ok = False
        reason = None
        try:
            if Path(pth).exists():
                txt = Path(pth).read_text(encoding="utf-8", errors="ignore")
                has_interface = bool(re.search(r"\binterface\s+\w+", txt))
                has_banner    = "// @ai-generated" in txt
                ok = has_interface and has_banner
                if not ok:
                    reason = f"interface={has_interface}, banner={has_banner}"
            else:
                reason = "file not found"
        except Exception as e:
            reason = redact_secret(str(e))
        results["pass" if ok else "fail"] += 1
        results["details"].append({"path": pth, "status": "pass" if ok else "fail", **({"reason": reason} if reason else {})})

    out_dir = Path("reports") / "review"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"validate_{ts}.json"
    md_path_out = out_dir / f"validate_{ts}.md"

    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    # Pretty MD
    lines = [f"# Validation Results ({ts})", "", f"Source: {suggestions_md_path}", ""]
    lines.append(f"**Pass:** {results['pass']}  |  **Fail:** {results['fail']}")
    lines.append("")
    lines.append("| Path | Status | Notes |")
    lines.append("|--|--|--|")
    for d in results["details"]:
        notes = d.get("reason", "")
        lines.append(f"| {d['path']} | {d['status']} | {notes} |")
    md_path_out.write_text("\n".join(lines), encoding="utf-8")

    return {
        "ok": True,
        "output_json": str(json_path),
        "output_md": str(md_path_out),
        "summary": {"pass": results["pass"], "fail": results["fail"], "count": len(results["details"])}
    }

# ── Legacy shims for UI/swagger parity (non-invasive wrappers) ────────────────
@app.post("/audit/js/plan")
async def legacy_audit_plan():
    return await scan_files()

@app.post("/audit/js/dry-run")
async def legacy_audit_dry_run(root: str = "src", limit: int = 100):
    req = ConvertTreeRequest(root=root, provider="auto", model=None, limit=limit, dry_run=True)
    return await convert_tree(req)

@app.post("/audit/js/convert")
async def legacy_audit_convert(root: str = "src", limit: int = 100):
    req = ConvertTreeRequest(root=root, provider="auto", model=None, limit=limit, dry_run=False)
    return await convert_tree(req)

@app.get("/orchestrator/artifacts/generate")
async def legacy_artifacts_generate():
    out = []
    for p in (Path("reports") / "suggestions").glob("*.md"):
        out.append(str(p))
    return {"suggestions": out}

# ── Factory ───────────────────────────────────────────────────────────────────
def create_app():
    return app
