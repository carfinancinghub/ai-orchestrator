"""
Path: core/providers/__init__.py
"""
from __future__ import annotations
from typing import Optional
from .base import LLMProvider
from .echo import EchoProvider

_PROVIDERS = {"echo": EchoProvider}

def load_provider(name: Optional[str]) -> Optional[LLMProvider]:
    if not name:
        return None
    cls = _PROVIDERS.get(name.strip().lower())
    return cls() if cls else None

__all__ = ["LLMProvider", "load_provider", "EchoProvider"]
