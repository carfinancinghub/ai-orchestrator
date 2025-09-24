"""COD1 scaffold: Grok provider wrapper (non-destructive)."""
from os import getenv
def review_stub(text: str) -> dict:
    return {
        "provider": "grok",
        "ok": bool(getenv("GROK_API_KEY")),
        "note": "scaffold only",
    }