Set-Location 'C:\c\ai-orchestrator'
New-Item -ItemType Directory -Force -Path .\app\core | Out-Null
@'
import os
from typing import Optional

try:
    import openai
    _openai_ok = True
except Exception:
    _openai_ok = False

try:
    import google.generativeai as genai
    _gemini_ok = True
except Exception:
    _gemini_ok = False

class LLMAdapter:
    def __init__(self, provider: str, api_key: Optional[str] = None):
        self.provider = provider.lower()
        if self.provider == "openai" and _openai_ok:
            openai.api_key = api_key or os.getenv("OPENAI_API_KEY") or ""
        elif self.provider == "gemini" and _gemini_ok:
            genai.configure(api_key=api_key or os.getenv("GEMINI_API_KEY") or "")
        elif self.provider == "grok":
            self._xai_key = api_key or os.getenv("XAI_API_KEY") or ""

    def convert(self, prompt: str) -> str:
        if self.provider == "openai" and _openai_ok:
            resp = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            return resp.choices[0].message.content or ""
        if self.provider == "gemini" and _gemini_ok:
            model = genai.GenerativeModel("gemini-1.5-pro")
            resp = model.generate_content(prompt)
            return getattr(resp, "text", "") or ""
        if self.provider == "grok":
            # TODO: xAI call
            return ""
        return ""

    def review(self, prompt: str) -> str:
        return self.convert(prompt)
'@ | Set-Content -Path .\app\core\llm_adapters.py -Encoding UTF8
