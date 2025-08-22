# Path: core/providers/__init__.py
# Purpose: Provider registry + loader.

from __future__ import annotations
from typing import Optional, Type

from .base import LLMProvider
from .echo import EchoProvider
from .upper import UpperProvider

_PROVIDERS: dict[str, Type[LLMProvider]] = {
    "echo": EchoProvider,
    "upper": UpperProvider,
}

def load_provider(name: Optional[str]) -> Optional[LLMProvider]:
    if not name:
        return None
    cls = _PROVIDERS.get(name.strip().lower())
    return cls() if cls else None
