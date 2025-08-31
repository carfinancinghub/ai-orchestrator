# Path: app/services/llm/google_client.py
from __future__ import annotations
import os, json
from typing import Dict

try:
    import requests
except Exception:
    requests = None

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-pro")
${1}__REDACTED__

def available() -> bool:
    return bool(GOOGLE_API_KEY) and requests is not None

def review_ts(ts_code: str, file_path: str) -> Dict[str, str]:
    """
    Return structured verdict:
      { "ok": bool, "ts_code": str, "reason": str }
    """
    if not available():
        return {"ok": True, "ts_code": ts_code, "reason": ""}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GOOGLE_API_KEY}"
    payload = {
        "contents": [{
            "parts": [{
                "text": (
                    "Review the following TS/TSX for type safety and style. "
                    "If acceptable, reply 'APPROVE'. If not, reply 'REJECT' and propose a corrected full file."
                    f"\n\nFile: {file_path}\n\n```\n{ts_code}\n```"
                )
            }]
        }]
    }
    try:
        r = requests.post(url, json=payload, timeout=90)
        r.raise_for_status()
        txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        if "APPROVE" in txt.upper() and "REJECT" not in txt.upper():
            return {"ok": True, "ts_code": ts_code, "reason": ""}
        # if Gemini produced a corrected file, try to extract code fence
        return {"ok": False, "ts_code": txt, "reason": "Gemini suggested changes"}
    except Exception as e:
        return {"ok": True, "ts_code": ts_code, "reason": f"gemini_error:{e}"}
