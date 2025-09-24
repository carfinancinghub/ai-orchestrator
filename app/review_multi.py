# app/review_multi.py
from __future__ import annotations
import json, os, time, pathlib
from typing import Iterable, Dict, Any, List

# ---------- Tier routing ----------
TIERS = ("Free", "Premium", "Wow++")

def _baseline_score(path: str) -> int:
    try:
        sz = os.path.getsize(path)
    except OSError:
        sz = 0
    base = 40 + min(50, sz // 5_000)  # 0..+50 by size
    if path.endswith((".ts", ".tsx")): base += 5
    return int(max(0, min(100, base)))

def _avg(nums: List[int]) -> int:
    if not nums: return 0
    return max(0, min(100, int(round(sum(nums)/len(nums)))))

# ---------- Providers (all optional, soft-fail) ----------
def _allow(provider_name: str) -> bool:
    raw = os.getenv("AIO_PROVIDERS", "").strip()
    if not raw:
        return True  # default: allow all if not specified
    allowed = {p.strip().lower() for p in raw.split(",") if p.strip()}
    return provider_name.lower() in allowed

def _openai_chat(prompt: str, model: str="gpt-4o-mini") -> Dict[str, Any]:
    if not _allow("OpenAI"): return {"ok": False, "note": "disabled via AIO_PROVIDERS"}
    key = os.getenv("OPENAI_API_KEY")
    if not key: return {"ok": False, "note": "OPENAI_API_KEY missing"}
    try:
        # prefer new SDK if available
        try:
            from openai import OpenAI
            client = OpenAI(api_key=key)
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role":"system","content":"You are a strict TypeScript code reviewer. Respond JSON with fields: summary, score(0-100)."},
                          {"role":"user",   "content": prompt}],
                temperature=0.2,
            )
            content = resp.choices[0].message.content or ""
        except Exception:
            # fallback to legacy SDK if installed as `openai`
            import openai  # type: ignore
            openai.api_key = key
            resp = openai.ChatCompletion.create(
                model=model,
                messages=[{"role":"system","content":"You are a strict TypeScript code reviewer. Respond JSON with fields: summary, score(0-100)."},
                          {"role":"user",   "content": prompt}],
                temperature=0.2,
            )
            content = resp.choices[0].message["content"] or ""
        # try parse JSON from content; fallback to summary only
        try:
            data = json.loads(content)
            score = int(data.get("score", 60))
            summary = str(data.get("summary", "")).strip()
        except Exception:
            score, summary = 60, content.strip()
        return {"ok": True, "provider": "openai", "model": model, "summary": summary, "score": max(0, min(100, score))}
    except Exception as e:
        return {"ok": False, "note": f"openai err: {e.__class__.__name__}: {e}"}

def _gemini_review(prompt: str, model: str="gemini-1.5-flash") -> Dict[str, Any]:
    if not _allow("Gemini"): return {"ok": False, "note": "disabled via AIO_PROVIDERS"}
    key = os.getenv("GEMINI_API_KEY")
    if not key: return {"ok": False, "note": "GEMINI_API_KEY missing"}
    try:
        import google.generativeai as genai  # type: ignore
        genai.configure(api_key=key)
        m = genai.GenerativeModel(model)
        r = m.generate_content(prompt)
        text = (getattr(r, "text", None) or getattr(r, "candidates", [{}])[0].get("content", "") or "").strip()
        # naive score scrape
        score = 65
        return {"ok": True, "provider":"gemini", "model": model, "summary": text, "score": score}
    except Exception as e:
        return {"ok": False, "note": f"gemini err: {e.__class__.__name__}: {e}"}

def _grok_review(prompt: str, model: str="grok-beta") -> Dict[str, Any]:
    if not _allow("Grok"): return {"ok": False, "note": "disabled via AIO_PROVIDERS"}
    key = os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY")
    if not key: return {"ok": False, "note": "GROK_API_KEY/XAI_API_KEY missing"}
    try:
        # simple HTTPS call; avoid requiring a specific SDK
        import requests  # type: ignore
        url = "https://api.x.ai/v1/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role":"system","content":"You are an optimization reviewer. Respond JSON with fields: summary, score(0-100)."},
                {"role":"user","content": prompt},
            ],
            "temperature": 0.2
        }
        resp = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json=payload, timeout=30)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        try:
            data = json.loads(content)
            score = int(data.get("score", 70))
            summary = str(data.get("summary", "")).strip()
        except Exception:
            score, summary = 70, content.strip()
        return {"ok": True, "provider":"grok", "model": model, "summary": summary, "score": max(0, min(100, score))}
    except Exception as e:
        return {"ok": False, "note": f"grok err: {e.__class__.__name__}: {e}"}

# ---------- Tier prompts ----------
def _mk_prompt(kind: str, rel_path: str, text: str) -> str:
    if kind == "free":
        return f"""File: {rel_path}
Task: Quick value check and function/type sanity. Return JSON: {{ "summary": "...", "score": 0-100 }}.
Code:
{text[:6000]}"""
    if kind == "premium":
        return f"""File: {rel_path}
Task: Type inference & refactor suggestions focusing on props, event handlers, and state. Return JSON: {{ "summary": "...", "score": 0-100 }}.
Code:
{text[:6000]}"""
    # wow++
    return f"""File: {rel_path}
Task: System-level & perf insights (structure, lazy-loading, memoization, bundle impact). Return JSON: {{ "summary": "...", "score": 0-100 }}.
Code:
{text[:6000]}"""

# ---------- Main entry ----------
def run(files: Iterable[str], run_id: str, root: str) -> list[str]:
    out_links: List[str] = []
    root_abs = os.path.abspath(root)
    out_root = os.path.join("artifacts", "reviews", run_id)

    for f in files:
        absf = os.path.abspath(f)
        try:
            rel = os.path.relpath(absf, root_abs) if absf.startswith(root_abs) else os.path.basename(absf)
        except Exception:
            rel = os.path.basename(absf)
        # read source
        try:
            with open(absf, "r", encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        except Exception:
            text = ""

        base_score = _baseline_score(absf)

        # --- Free: OpenAI quick pass
        free_res = _openai_chat(_mk_prompt("free", rel, text), model=os.getenv("AIO_MODEL","gpt-4o-mini")) if _allow("OpenAI") else {"ok": False, "note": "OpenAI disabled"}
        # --- Premium: OpenAI deeper pass
        premium_res = _openai_chat(_mk_prompt("premium", rel, text), model=os.getenv("AIO_MODEL","gpt-4o-mini")) if _allow("OpenAI") else {"ok": False, "note": "OpenAI disabled"}
        # --- Wow++: Gemini + Grok
        wow_gem = _gemini_review(_mk_prompt("wow", rel, text)) if _allow("Gemini") else {"ok": False, "note": "Gemini disabled"}
        wow_grk = _grok_review(_mk_prompt("wow", rel, text))    if _allow("Grok")   else {"ok": False, "note": "Grok disabled"}

        # aggregate scores per tier
        free_score   = _avg([base_score] + ([free_res.get("score", 0)] if free_res.get("ok") else []))
        prem_score   = _avg([base_score] + ([premium_res.get("score", 0)] if premium_res.get("ok") else []))
        wow_scores   = [base_score] + [r.get("score", 0) for r in (wow_gem, wow_grk) if r.get("ok")]
        wow_score    = _avg(wow_scores)

        # write each tier JSON
        def _write(tier: str, payload: Dict[str, Any]) -> None:
            outp = os.path.join(out_root, tier, rel + ".json")
            os.makedirs(os.path.dirname(outp), exist_ok=True)
            with open(outp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            out_links.append(outp)

        _write("Free", {
            "file": rel, "tier": "Free", "provider": "openai", "ok": bool(free_res.get("ok")),
            "model": free_res.get("model", os.getenv("AIO_MODEL","gpt-4o-mini")),
            "summary": free_res.get("summary") or free_res.get("note", "offline/stub"),
            "worth_score": free_score, "ts": int(time.time()),
        })
        _write("Premium", {
            "file": rel, "tier": "Premium", "provider": "openai", "ok": bool(premium_res.get("ok")),
            "model": premium_res.get("model", os.getenv("AIO_MODEL","gpt-4o-mini")),
            "summary": premium_res.get("summary") or premium_res.get("note", "offline/stub"),
            "worth_score": prem_score, "ts": int(time.time()),
        })
        _write("Wow++", {
            "file": rel, "tier": "Wow++", "providers": {
                "gemini": {"ok": bool(wow_gem.get("ok")), "model": wow_gem.get("model"), "note": wow_gem.get("note"), "summary": wow_gem.get("summary")},
                "grok":   {"ok": bool(wow_grk.get("ok")), "model": wow_grk.get("model"), "note": wow_grk.get("note"), "summary": wow_grk.get("summary")},
            },
            "worth_score": wow_score, "ts": int(time.time()),
        })

    return out_links
