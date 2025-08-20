from fastapi.testclient import TestClient
from app.server import app

client = TestClient(app)

def test_routes_exist():
    r = client.get("/_debug/routes")
    assert r.status_code == 200
    paths = set(r.json()["paths"])
    for p in {"/orchestrator/status", "/orchestrator/run-all",
              "/orchestrator/run-stage/{stage}", "/convert/discover", "/convert/file"}:
        assert p in paths

def test_generate_stage():
    r = client.post("/orchestrator/run-stage/generate")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") in ("OK", "FLAG", "PASS", "OK")  # minimal sanity
