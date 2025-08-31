# Path: app/services/llm/orchestrator.py
from __future__ import annotations
from typing import Dict

from .sparka_client import SparkaClient
from .openai_client import convert_js_to_ts as oai_convert, generate_tests as oai_tests
from .google_client import review_ts as gemini_review
from .grok_client import arbitrate as grok_arbitrate, fix_it as grok_fix

_sparka = SparkaClient()

def _maybe_sparka(op: str, *args, **kwargs):
    """Try Sparka first; return str or None on failure."""
    try:
        if op == "convert":
            return _sparka.convert_js_to_ts(*args, **kwargs)
        if op == "tests":
            return _sparka.generate_tests(*args, **kwargs)
        if op == "review":
            return _sparka.review(*args, **kwargs)
        if op == "arbitrate":
            return _sparka.arbitrate(*args, **kwargs)
        if op == "evaluate":
            return _sparka.evaluate(*args, **kwargs)
    except Exception:
        return None
    return None

def orchestrate_conversion_pipeline(
    repo_name: str,
    platform: str,
    token: str,
    src_path: str,
    js_code: str,
    test_hint: str = "",
    doc_hint: str = "",
) -> Dict[str, str]:
    # 1) Convert (Sparka → OpenAI)
    ts_code = _maybe_sparka("convert", js_code, src_path) or oai_convert(js_code, src_path)
    # 2) Tests (Sparka → OpenAI)
    test_code = _maybe_sparka("tests", ts_code, src_path) or oai_tests(ts_code, src_path)
    # 3) Review (Sparka → Gemini) then arbitration (Sparka → Grok)
    reviewed = _maybe_sparka("review", ts_code, src_path)
    if reviewed:
        if reviewed.strip().lower().startswith("ok"):
            pass
        else:
            ts_code = reviewed
    else:
        verdict = gemini_review(ts_code, src_path)
        if not verdict.get("ok", True):
            ts_code = _maybe_sparka("arbitrate", verdict.get("ts_code", ts_code), verdict.get("reason","rejected"), src_path) \
                      or grok_arbitrate(verdict.get("ts_code", ts_code), verdict.get("reason","rejected"), src_path)
        else:
            ts_code = verdict.get("ts_code", ts_code)

    # 4) Final small fix pass (Sparka → Grok)
    fixed = _maybe_sparka("arbitrate", ts_code, "final polish", src_path)
    ts_code = fixed or grok_fix(ts_code, src_path)
    return {"ts_code": ts_code, "test_code": test_code}

def evaluate_ts(ts_code: str, file_path: str) -> Dict:
    """Quality evaluation for existing TS/TSX files against CFH standards."""
    out = _maybe_sparka("evaluate", ts_code, file_path)
    if out:
        action = "update" if "no-op" not in out.lower() else "no-op"
        return {"action": action, "ts_code": out if action == "update" else ts_code}
    # Fallback: Grok arbitrate-style
    prompt = (
        "Evaluate TS/TSX for CFH standards:\n"
        "- Use @ imports where configured\n"
        "- Avoid `any`; prefer strict, explicit types\n"
        "- Idiomatic React patterns where applicable\n"
        "- Return a FULL corrected file if updates are needed; otherwise reply 'NO-OP'.\n\n"
        f"File: {file_path}\n```typescript\n{ts_code}\n```"
    )
    out = grok_arbitrate(prompt, "Evaluate", file_path)
    action = "update" if "no-op" not in out.lower() else "no-op"
    return {"action": action, "ts_code": out if action=="update" else ts_code}
