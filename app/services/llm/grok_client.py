# Path: app/services/llm/grok_client.py
from __future__ import annotations
import os
import json

try:
    import requests
except Exception:
    requests = None

XAI_API_KEY = os.getenv("XAI_API_KEY","")
XAI_MODEL = os.getenv("XAI_MODEL","grok-beta")

def available() -> bool:
    return bool(XAI_API_KEY) and requests is not None

def arbitrate(ts_code: str, reason: str, file_path: str) -> str:
    """
    Ask Grok to arbitrate when Gemini rejects. If offline, pass-through.
    """
    if not available():
        return ts_code
    # Placeholder per https://x.ai/api — actual schema may differ
    url = "https://api.x.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {XAI_API_KEY}", "Content-Type": "application/json"}
    prompt = (
        "Arbitrate: Gemini reviewer rejected the TS file. "
        f"Reason: {reason}\n"
        "Provide the best corrected full TS/TSX file or approve the original if correct.\n\n"
        f"File: {file_path}\n\n```\n{ts_code}\n```"
    )
    payload = {"model": XAI_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.1}
    try:
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=90)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]
    except Exception:
        return ts_code

def fix_it(ts_code: str, file_path: str) -> str:
    # simple pass-through fixer (optionally used elsewhere)
    return ts_code
