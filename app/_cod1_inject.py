"""COD1 optional injector.

- Monkeypatch subprocess.run to default to UTF-8 errors="replace" (avoids UnicodeDecodeError).
- Exposes enable_cod1() callable. If ops.py imports this, the setting is applied early.
"""
import subprocess as _sp
_orig_run = _sp.run

def _safe_run(*a, **k):
    # keep caller flags, but ensure decoding is safe
    if "encoding" not in k and "text" not in k:
        k["encoding"] = "utf-8"
        k["errors"] = "replace"
        k["text"] = True
    else:
        k["errors"] = "replace"
    return _orig_run(*a, **k)

def enable_cod1():
    try:
        _sp.run = _safe_run
    except Exception:
        pass