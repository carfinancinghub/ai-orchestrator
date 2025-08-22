# Path: tests/test_js_auditor.py
from pathlib import Path
from core.js_auditor import JSAuditor

MD_JS = """
| File Path | Size (bytes) | Last Write Time |
|-----------|--------------|-----------------|
| C:/proj/ui/App.js | 100 | 2025-06-01 10:00:00 |
| C:/proj/ui/App.jsx | 120 | 2025-06-01 10:01:00 |
| C:/proj/ui/Widget.jsx | 200 | 2025-06-01 10:02:00 |
| C:/proj/ui/Widget.jsx | 200 | 2025-06-01 10:01:00 |
| C:/proj/ui/Chart.test.jsx | 90 | 2025-06-01 10:03:00 |
"""

MD_TS = """
| File Path | Size (bytes) | Last Write Time |
|-----------|--------------|-----------------|
| C:/proj/ui/App.tsx | 150 | 2025-06-02 10:00:00 |
"""

def _write(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_plan_dedup_and_conversion(tmp_path: Path):
    a = JSAuditor()
    f1 = tmp_path/"js.md"; _write(f1, MD_JS)
    f2 = tmp_path/"ts.md"; _write(f2, MD_TS)
    entries = a.parse_md_files([str(f1), str(f2)])
    plan = a.plan(entries)

    # App has TSX variant => drop js/jsx, keep tsx
    assert any(p.endswith("App.tsx") for p in plan["keep_ts_tsx"]) \
        and not any(p.endswith("App.jsx") for p in plan["convert_candidates"]) \
        and not any(p.endswith("App.js") for p in plan["convert_candidates"]) \
        and any(p.endswith("App.jsx") for p in plan["drop_js_already_converted"]) \
        and any(p.endswith("App.js") for p in plan["drop_js_already_converted"]) 

    # Widget has no TS variant => suggests conversion; test files skipped
    assert any(p.endswith("Widget.jsx") for p in plan["convert_candidates"]) \
        and not any("Chart.test.jsx" in p for p in plan["convert_candidates"]) \
        and any("Chart.test.jsx" in p for p in plan["tests_skipped"]) 
