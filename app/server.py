from __future__ import annotations

import os
import json
import time
from pathlib import Path
from typing import List, Optional, Dict, Any, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import httpx
from openai import AsyncOpenAI

# ── Env / app ──────────────────────────────────────────────────────────────────
load_dotenv()

app = FastAPI(title="CFH AI Orchestrator", version="0.3.0")

# CORS (adjust origins if needed)
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

# Providers: OpenAI + xAI (Grok via OpenAI-compatible) + Gemini (REST)
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

XAI_KEY = os.getenv("XAI_GROK_API_KEY") or os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY")
XAI_BASE_URL = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")

GOOGLE_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
GEMINI_BASE = os.getenv("GEMINI_BASE", "https://generativelanguage.googleapis.com/v1beta")

# Clients (created only if keys exist)
openai_client: Optional[AsyncOpenAI] = AsyncOpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None
xai_client: Optional[AsyncOpenAI] = (
    AsyncOpenAI(api_key=XAI_KEY, base_url=XAI_BASE_URL) if XAI_KEY else None
)

# ── Schemas ───────────────────────────────────────────────────────────────────
class ConvertRequest(BaseModel):
    file_path: str = Field(..., description="Path to a .js or .jsx file")
    provider: Optional[str] = Field(None, description="openai | grok | google | anthropic")
    model: Optional[str] = Field(None, description="Provider-specific model")

class ConvertResponse(BaseModel):
    saved_to: str
    bytes: int

# Batch conversion request/response
class ConvertTreeRequest(BaseModel):
    root: str = Field(default="src")
    provider: Literal["openai", "grok", "google", "anthropic"] = "openai"
    model: str | None = None
    limit: int | None = Field(default=None, description="Optional max files to convert this run")
    dry_run: bool = Field(default=False, description="If true, do not write files; just preview")

class ConvertTreeResponse(BaseModel):
    ok: bool
    provider: str
    model: str | None
    converted: list[str]
    skipped: list[str]
    dry_run: bool
    metrics: Dict[str, Any]

# ── Utils ─────────────────────────────────────────────────────────────────────
SkipDirs = {"node_modules", ".venv", "venv", "dist", "build", ".git", "__pycache__", ".next", "coverage", "out", "release", "tmp", "temp"}

def should_skip(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    return any(sd in parts for sd in SkipDirs)

def find_js_targets(root: Path) -> list[Path]:
    targets: list[Path] = []
    if not root.exists():
        return targets
    for p in root.rglob("*"):
        if p.is_dir():
            continue
        if should_skip(p):
            continue
        ext = p.suffix.lower()
        if ext not in (".js", ".jsx"):
            continue
        # skip if sibling .ts/.tsx already exists
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

async def _convert_openai(model: str, prompt: str) -> str:
    if not openai_client:
        raise RuntimeError("OPENAI_API_KEY not configured")
    resp = await openai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a senior TypeScript migration assistant."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content or ""

async def _convert_grok(model: str, prompt: str) -> str:
    if not xai_client:
        raise RuntimeError("XAI_GROK_API_KEY not configured")
    resp = await xai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a senior TypeScript migration assistant."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content or ""

async def _convert_gemini(model: str, prompt: str) -> str:
    if not GOOGLE_KEY:
        raise RuntimeError("GOOGLE_API_KEY/GEMINI_API_KEY not configured")
    url = f"{GEMINI_BASE}/models/{model}:generateContent?key={GOOGLE_KEY}"
    payload = {
        "contents": [
            {"parts": [{"text": "You are a senior TypeScript migration assistant."}]},
            {"parts": [{"text": prompt}]},
        ]
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
    # Extract first candidate text
    try:
        return (
            data["candidates"][0]["content"]["parts"][0]["text"]  # type: ignore[index]
        )
    except Exception:
        # If schema differs, dump for debugging
        return f"// gemini response parse error\n/* {json.dumps(data)[:2000]} */"

async def _convert_with_provider_js_to_ts(
    src_path: Path,
    provider: str,
    model: str | None,
) -> str:
    """
    Returns TS/TSX code string (without banner).
    If provider key missing, returns original code as a no-op fallback.
    """
    js_code = src_path.read_text(encoding="utf-8")

    # Provider-key checks
    have_openai = bool(OPENAI_KEY)
    have_grok = bool(XAI_KEY)
    have_google = bool(GOOGLE_KEY)
    have_anthropic = False  # reserved

    key_missing = (
        (provider == "openai" and not have_openai) or
        (provider == "grok" and not have_grok) or
        (provider == "google" and not have_google) or
        (provider == "anthropic" and not have_anthropic)
    )
    if key_missing:
        return js_code  # offline fallback

    prompt = _build_prompt(js_code)

    # Minimal provider switch; reuse existing helpers
    if provider == "openai":
        return await _convert_openai(model or "gpt-4o-mini", prompt)
    if provider == "grok":
        return await _convert_grok(model or "grok-2-latest", prompt)
    if provider == "google":
        return await _convert_gemini(model or "gemini-1.5-pro", prompt)

    # TODO: Anthropic when ready. For now: no-op.
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
    }

@app.get("/orchestrator/scan")
async def scan_files():
    root = Path("src")
    if not root.exists():
        return {"files": [], "count": 0}
    files: List[str] = [str(p) for p in root.rglob("*.js")] + [str(p) for p in root.rglob("*.jsx")]
    return {"files": files, "count": len(files)}

@app.post("/convert/file", response_model=ConvertResponse)
async def convert_file(req: ConvertRequest):
    path = Path(req.file_path)
    if not path.exists() or path.suffix.lower() not in (".js", ".jsx"):
        raise HTTPException(status_code=404, detail="File not found or not JS/JSX")

    js_code = path.read_text(encoding="utf-8")
    prompt = _build_prompt(js_code)

    provider = (req.provider or os.getenv("LLM_PROVIDER") or "openai").lower()
    model = req.model or os.getenv("LLM_MODEL") or (
        "gpt-4o-mini" if provider == "openai"
        else "grok-2-latest" if provider == "grok"
        else "gemini-1.5-pro"
    )

    try:
        if provider == "openai" and OPENAI_KEY:
            ts_code = await _convert_openai(model, prompt)
            banner = "// @ai-generated by OpenAI\n"
        elif provider == "grok" and XAI_KEY:
            ts_code = await _convert_grok(model, prompt)
            banner = "// @ai-generated by xAI Grok\n"
        elif provider == "google" and GOOGLE_KEY:
            ts_code = await _convert_gemini(model, prompt)
            banner = "// @ai-generated by Google Gemini\n"
        else:
            # Unknown provider or missing key → offline fallback
            ts_path = _offline_write(path, js_code, provider_note=provider)
            return ConvertResponse(saved_to=str(ts_path), bytes=ts_path.stat().st_size)

        ts_path = _ts_path_for(path)
        ts_path.write_text(banner + (ts_code or ""), encoding="utf-8")
        return ConvertResponse(saved_to=str(ts_path), bytes=ts_path.stat().st_size)

    except Exception as e:
        # If provider request fails, fall back to offline copy to keep you moving.
        ts_path = _offline_write(path, js_code, provider_note=f"{provider}-error:{type(e).__name__}")
        return ConvertResponse(saved_to=str(ts_path), bytes=ts_path.stat().st_size)

# NEW: Batch conversion endpoint ------------------------------------------------
@app.post("/convert/tree", response_model=ConvertTreeResponse)
async def convert_tree(req: ConvertTreeRequest):
    started = time.time()
    root = Path(req.root)
    targets = find_js_targets(root)
    if req.limit:
        targets = targets[: req.limit]

    converted: list[str] = []
    skipped: list[str] = []
    banner = "// @ai-generated\n"

    for p in targets:
        try:
            ts_ext = ".ts" if p.suffix.lower() == ".js" else ".tsx"
            out_path = p.with_suffix(ts_ext)
            ts_code = await _convert_with_provider_js_to_ts(p, req.provider, req.model)
            if req.dry_run:
                skipped.append(str(p))
                continue
            out_path.write_text(banner + ts_code, encoding="utf-8")
            converted.append(str(out_path))
        except Exception as e:
            skipped.append(f"{p} :: {e}")

    metrics = {
        "files_considered": len(targets),
        "converted_count": len(converted),
        "skipped_count": len(skipped),
        "elapsed_sec": round(time.time() - started, 3),
        "provider": req.provider,
        "model": req.model,
    }
    return ConvertTreeResponse(
        ok=True,
        provider=req.provider,
        model=req.model,
        converted=converted,
        skipped=skipped,
        dry_run=req.dry_run,
        metrics=metrics,
    )


def create_app():
    return app
