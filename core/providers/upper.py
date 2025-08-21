"""
Path: core/providers/upper.py
Description: Simple provider that uppercases the prompt with a prefix.
"""
from __future__ import annotations
from .base import LLMProvider

class UpperProvider(LLMProvider):
    def generate(self, prompt: str) -> str:
        # Why: prove pluggability with a different, visible transformation
        return f"UPPER: {prompt.upper()}".rstrip()
