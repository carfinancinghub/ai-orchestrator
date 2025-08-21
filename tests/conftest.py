import pytest

@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("AIO_PROVIDER", "echo")
    monkeypatch.setenv("AIO_DRY_RUN", "false")
    yield
