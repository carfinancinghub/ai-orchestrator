# === AI‑ORCH HEADER ===
# File: src/hello.py
# Purpose: Minimal module so pytest has something real to run.
# Notes: Safe example for the pipeline’s first acceptance.
from __future__ import annotations


def greet(name: str) -> str:
    """Return a friendly greeting."""
    name = (name or "world").strip() or "world"
    return f"Hello, {name}!"