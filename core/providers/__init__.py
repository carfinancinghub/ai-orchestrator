from __future__ import annotations
from typing import Optional
from .base import LLMProvider
from .echo import EchoProvider

def load_provider(name: Optional[str]) -> Optional[LLMProvider]:
    if not name:
        return None
    key = name.strip().lower()
    if key == "echo":
        return EchoProvider()
    # TODO: add "openai", "azure", "openrouter", "ollama", ...
    return None
