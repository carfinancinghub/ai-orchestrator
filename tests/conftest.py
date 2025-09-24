# Path: tests/conftest.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # ensure project root on sys.path

import pytest
@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("AIO_PROVIDER", "echo")
    monkeypatch.setenv("AIO_DRY_RUN", "false")
    yield
