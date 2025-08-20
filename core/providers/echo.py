from __future__ import annotations
from .base import LLMProvider

class EchoProvider(LLMProvider):
    def generate(self, prompt: str) -> str:
        return f"ECHO: {prompt}"
