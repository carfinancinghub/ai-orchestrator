# Path: app/services/llm/sparka_client.py
"""
Sparka AI integration (bridge-first design).

How it works:
- Tries to call a small Node bridge (app/services/llm/sparka_bridge.mjs) that
  uses Vercel AI SDK (or falls back to OpenAI HTTP) to run prompts.
- Reads keys from env; optionally loads ".env.local" if present (simple parser).
- If Node or keys are missing, returns None → orchestrator falls back to other providers.

Install (in repo root):
  npm i @vercel/ai openai            # preferred (Vercel AI SDK + OpenAI)
  # or, if you prefer the package name SG Man used:
  # npm i @vercel/ai-chatbot         # (we still fall back gracefully)

Require Node >= 18.
"""
from __future__ import annotations
import json
import os
import subprocess
from pathlib import Path
from typing import Optional

ENV_HINTS = ("OPENAI_API_KEY", "SPARKA_API_KEY", "GROK_API_KEY", "GOOGLE_API_KEY")

def _load_env_local():
    p = Path(".env.local")
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and v and k not in os.environ:
            os.environ[k] = v

def _node_available() -> bool:
    try:
        subprocess.run(["node", "-v"], capture_output=True, check=True)
        return True
    except Exception:
        return False

def _run_bridge(op: str, file_path: str, code: str, extra: Optional[dict] = None, timeout: int = 120) -> Optional[str]:
    """
    Calls the node bridge with JSON on stdin and returns stdout string (or None).
    """
    bridge = Path("app/services/llm/sparka_bridge.mjs")
    if not bridge.exists() or not _node_available():
        return None
    _load_env_local()
    payload = {
        "op": op,
        "file_path": file_path,
        "code": code,
        "extra": extra or {},
        # Pass keys the bridge might need
        "env": {k: os.getenv(k, "") for k in ENV_HINTS},
    }
    try:
        proc = subprocess.run(
            ["node", str(bridge)],
            input=json.dumps(payload).encode("utf-8"),
            capture_output=True,
            timeout=timeout,
            check=True,
        )
        out = proc.stdout.decode("utf-8", "replace").strip()
        return out or None
    except Exception:
        return None

class SparkaClient:
    """Thin wrapper around the bridge ops; returns None on any failure."""

    def convert_js_to_ts(self, js_code: str, file_path: str) -> Optional[str]:
        return _run_bridge("convert", file_path, js_code, timeout=180)

    def generate_tests(self, ts_code: str, file_path: str) -> Optional[str]:
        return _run_bridge("tests", file_path, ts_code, timeout=120)

    def review(self, ts_code: str, file_path: str) -> Optional[str]:
        return _run_bridge("review", file_path, ts_code, timeout=120)

    def arbitrate(self, text: str, reason: str, file_path: str) -> Optional[str]:
        return _run_bridge("arbitrate", file_path, text, extra={"reason": reason}, timeout=120)

    def evaluate(self, ts_code: str, file_path: str) -> Optional[str]:
        return _run_bridge("evaluate", file_path, ts_code, timeout=120)
