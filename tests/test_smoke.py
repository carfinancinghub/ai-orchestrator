from fastapi.testclient import TestClient
from aio_app.server import app

client = TestClient(app)

def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert "AI Orchestrator is running!" in r.json().get("message", "")

def test_routes_list():
    r = client.get("/_debug/routes")
    assert r.status_code == 200
    paths = r.json()["paths"]
    assert "/orchestrator/status" in paths
    assert "/convert/discover" in paths
