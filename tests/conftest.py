
""" path: tests/conftest.py """

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch):
# ensure echo path end-to-end
monkeypatch.setenv("AIO_PROVIDER", "echo")
monkeypatch.setenv("AIO_DRY_RUN", "false")
yield
