"""
Path: test/test_providers_upper.py
"""

from core.providers import load_provider
from core.providers.upper import UpperProvider

def test_load_provider_upper():
    p = load_provider("upper")
    assert isinstance(p, UpperProvider)
    assert p.generate("Hello, World!").startswith("UPPER: ")
    assert "HELLO" in p.generate("Hello")
