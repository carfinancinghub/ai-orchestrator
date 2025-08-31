# Path: tests/test_llm_pipeline.py
from __future__ import annotations
from app.services.llm.orchestrator import orchestrate_conversion_pipeline

def test_pipeline_smoke():
    js = "export function add(a,b){return a+b}"
    out = orchestrate_conversion_pipeline(
        repo_name="dummy/repo",
        platform="github",
        token="x",
        src_path="src/components/Button.jsx",
        js_code=js,
    )
    assert "ts_code" in out and "test_code" in out
    assert isinstance(out["ts_code"], str) and isinstance(out["test_code"], str)
