# Path: tests/test_validation.py
from __future__ import annotations
from app.services.validation.validate import run_full_validation

def test_validation_smoke():
    res = run_full_validation()
    assert "ok" in res
    assert "reasons" in res
