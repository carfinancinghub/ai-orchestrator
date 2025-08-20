""" Path: tests/test_api_generate.py """

from fastapi.testclient import TestClient
from app.server import app


def test_api_generate_echo_first_line():
c = TestClient(app)
r = c.post("/orchestrator/run-stage/generate")
assert r.status_code == 200
j = c.get("/orchestrator/artifacts/generate").json()
content = j.get("content", "")
assert content.splitlines()[0].startswith("ECHO: ")