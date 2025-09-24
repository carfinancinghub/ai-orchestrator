"""COD1 scaffold: Gemini provider wrapper (non-destructive).
Populate real calls using GEMINI_API_KEY if needed; returns a minimal review stub when called.
"""
from os import getenv
def review_stub(text: str) -> dict:
    return {
        "provider": "gemini",
        "ok": bool(getenv("GEMINI_API_KEY")),
        "note": "scaffold only",
    }