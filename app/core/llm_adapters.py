from __future__ import annotations

class LLMAdapter:
    def convert(self, prompt: str) -> str:
        return prompt

    def review(self, prompt: str) -> str:
        return self.convert(prompt)
