# Path: app/services/llm/openai_client.py
from __future__ import annotations
import os, json, re, time
from typing import List, Dict

try:
    import requests
except Exception:
    requests = None

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4")
${1}__REDACTED__

SYSTEM_CONVERT = """You are a senior TypeScript engineer. Convert JS/JSX to idiomatic TS/TSX.
- Keep runtime behavior identical
- Prefer explicit function signatures and Props types
- Avoid `any` unless truly unavoidable
- Preserve comments and TODO/FIXME
- .jsx -> .tsx, .js -> .ts
"""
SYSTEM_TESTS = """You are a senior test engineer. Write Jest tests for the supplied TS/TSX file.
- Deterministic tests; mock I/O and timers
- ≥70% coverage target
- Return ONLY a single fenced code block with the test file content.
"""

def available() -> bool:
    return bool(OPENAI_API_KEY) and requests is not None

def _chat(messages: List[Dict[str,str]], temperature: float = 0.2, max_tokens: int = 4000, retries: int = 3) -> str:
    if not available():
        return messages[-1].get("content","")
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": OPENAI_MODEL, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    for i in range(retries):
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=90)
        if r.status_code == 429 or 500 <= r.status_code < 600:
            time.sleep(2 ** i); continue
        try:
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]
        except Exception:
            if i < retries - 1: time.sleep(2 ** i); continue
            return messages[-1].get("content","")
    return messages[-1].get("content","")

def convert_js_to_ts(js_code: str, file_path: str) -> str:
    prompt = f"""Convert to TypeScript/TSX as appropriate.

File: {file_path}
JS/JSX:
```javascript
{js_code}
```"""
    out = _chat([{"role":"system","content": SYSTEM_CONVERT},{"role":"user","content": prompt}])
    return out or f"// converted (fallback)\n/* file: {file_path} */\n{js_code}"

def generate_tests(ts_code: str, file_path: str) -> str:
    prompt = f"""Generate Jest tests for the following TS/TSX module.

File: {file_path}
TS:
```typescript
{ts_code}
```"""
    out = _chat([{"role":"system","content": SYSTEM_TESTS},{"role":"user","content": prompt}], temperature=0.1, max_tokens=2000)
    m = re.search(r"```(?:typescript|ts|javascript|js|tsx)?\s*\n(.*?)\n```", out, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else out
