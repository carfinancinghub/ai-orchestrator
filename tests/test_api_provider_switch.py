""" 
Path: tests/test_api_provider_switch.py
"""

from fastapi.testclient import TestClient
from app.server import app

client = TestClient(app)

def _first_line():
    j = client.get("/orchestrator/artifacts/generate").json()
    return j.get("content", "").splitlines()[0] if j.get("content") else ""

def test_switch_between_echo_and_upper():
    # ensure upper
    r = client.post("/debug/provider", json={"provider": "upper"})
    assert r.status_code == 200
    r = client.post("/orchestrator/run-stage/generate")
    assert r.status_code == 200
    assert _first_line().startswith("UPPER: ")

    # switch to echo
    r = client.post("/debug/provider", json={"provider": "echo"})
    assert r.status_code == 200
    r = client.post("/orchestrator/run-stage/generate")
    assert r.status_code == 200
    assert _first_line().startswith("ECHO: ")
