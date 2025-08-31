# Path: tests/test_orchestrator_selection.py
from __future__ import annotations
from app.services.llm.orchestrator import orchestrate_conversion_pipeline

def test_dynamic_selection_smoke():
    js = "export function add(a,b){return a+b}"
    out = orchestrate_conversion_pipeline(
        repo_name="dummy/repo",
        platform="github",
        token="x",
        src_path="src/components/Button.jsx",
        js_code=js,
    )
    assert isinstance(out.get("ts_code"), str)
    assert isinstance(out.get("test_code"), str)
