# Path: tests/test_validate_targeted.py
from __future__ import annotations
from app.services.validation.validate import run_full_validation

def test_targeted_validation_smoke():
    res = run_full_validation(paths=["src/sample.ts"], test_path=None)
    assert "ok" in res and "reasons" in res
