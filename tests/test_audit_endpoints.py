"""
Path: tests/test_audit_endpoints.py
"""

from __future__ import annotations

from pathlib import Path
from fastapi.testclient import TestClient

from app.server import app


def _write_md(path: Path, rows: list[tuple[str, int, str]]) -> None:
    """
    Write a tiny markdown table:
      | <path> | <size> | <iso mtime> |
    """
    lines = ["| path | size | mtime |", "|---|---:|---|"]
    for p, sz, ts in rows:
        lines.append(f"| {p} | {sz} | {ts} |")
    path.write_text("\n".join(lines), encoding="utf-8")


def test_plan_and_convert_happy_path(tmp_path: Path):
    """
    Build a plan from two inventories and convert one in-root JS file.
    """
    # Create a tiny workspace with one JS (to convert) and one TS (to keep)
    ws = tmp_path / "ws"
    ws.mkdir()
    js_file = ws / "foo.js"
    js_file.write_text("export const add=(a,b)=>a+b;", encoding="utf-8")
    ts_keep = ws / "bar.ts"
    ts_keep.write_text("export const hello = ()=>'hi';", encoding="utf-8")

    # Fake inventories containing those two files
    md1 = tmp_path / "scan1.md"
    md2 = tmp_path / "scan2.md"
    _write_md(md1, [(str(js_file), 26, "2024-01-01T00:00:00")])
    _write_md(md2, [(str(ts_keep), 29, "2024-01-02T00:00:00")])

    c = TestClient(app)

    # Plan: prefer TS, convert remaining JS (in-root only)
    plan_req = {
        "md_paths": [str(md1), str(md2)],
        "workspace_root": str(ws),
        "size_min_bytes": 0,
        "exclude_regex": None,
        "same_dir_only": False,
    }
    r = c.post("/audit/js/plan", json=plan_req)
    assert r.status_code == 200
    plan = r.json()
    assert plan["counts"]["keep_ts_tsx"] == 1
    assert plan["counts"]["convert_in_root"] == 1
    assert plan["plan_path"].endswith(".txt")
    assert plan["csv_path"].endswith(".csv")

    # Convert the in-root candidates
    r2 = c.post("/audit/js/convert", json={"plan_path": plan["plan_path"], "write": True, "force": True})
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2["wrote"] == 1
    # Verify TS was written next to JS
    ts_out = js_file.with_suffix(".ts")
    assert ts_out.exists()
    # And it carries the original content (with our orchestrator header)
    assert "Converted from foo.js" in ts_out.read_text(encoding="utf-8")


def test_dry_run_and_commit(tmp_path: Path):
    """
    Dry-run previews a handful of conversions. Commit is a no-op in CI,
    but endpoint should respond sanely (GitOps optional).
    """
    ws = tmp_path / "root"
    ws.mkdir()
    f1 = ws / "x.jsx"
    f1.write_text("export default ()=>null;", encoding="utf-8")

    # Minimal plan JSON artifact
    plan_json = {
        "workspace_root": str(ws),
        "convert_candidates_in_root": [str(f1)],
        "counts": {"convert_in_root": 1},
    }
    c = TestClient(app)
    # Write plan as an artifact via /orchestrator/artifacts helper path is internal,
    # so we just save it where the API expects to read it.
    plan_path = tmp_path / "plan.txt"
    plan_path.write_text(__import__("json").dumps(plan_json), encoding="utf-8")

    # Dry-run
    r1 = c.post("/audit/js/dry-run", json={"plan_path": str(plan_path), "max_files": 1})
    assert r1.status_code == 200
    j1 = r1.json()
    assert j1["preview_count"] == 1
    assert j1["preview_path"].endswith(".txt")

    # Commit (will likely be dry/no-op unless GitOps is wired for tmp repo)
    r2 = c.post("/audit/js/commit", json={"plan_path": str(plan_path), "dry_run": True})
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2["dry_run"] is True
    assert j2["ts_existing"] in (0, 1)
