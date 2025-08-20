# === AI‑ORCH HEADER ===
# File: tests/test_hello.py
# Purpose: Unit tests for src/hello.py used by orchestrator QA.
# Notes: Kept intentionally simple.
from src.hello import greet


def test_greet_default():
    assert greet("") == "Hello, world!"


def test_greet_name():
    assert greet("Agasi") == "Hello, Agasi!"