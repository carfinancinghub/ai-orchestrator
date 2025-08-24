"""
Path: core/agent.py
Purpose: Local “Agent” that drives the auditor via HTTP:
  - builds a plan
  - decides dry-run vs convert based on thresholds/guards
  - commits if safe
Usage:
  python -m core.agent --root "C:\\Backup_Projects\\CFH" --port 8010 --max-writes 500 --threshold 1200
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import requests


def _post(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()


def run(root: str, port: int, md_paths: List[str], size_min_bytes: int, exclude_regex: str | None,
        same_dir_only: bool, threshold: int, max_writes: int | None, commit: bool) -> None:
    base = f"http://127.0.0.1:{port}"
    plan_req = {
        "md_paths": md_paths,
        "workspace_root": root,
        "size_min_bytes": size_min_bytes,
        "exclude_regex": exclude_regex or None,
        "same_dir_only": bool(same_dir_only),
    }
    plan = _post(f"{base}/audit/js/plan", plan_req)
    counts = plan.get("counts", {})
    in_root = int(counts.get("convert_in_root") or 0)
    print(f"[agent] plan: convert_in_root={in_root} total_candidates={counts.get('convert_candidates')}")

    if in_root > threshold:
        print(f"[agent] too many to write ({in_root} > {threshold}); doing dry-run preview of 20")
        _ = _post(f"{base}/audit/js/dry-run", {"plan_path": plan["plan_path"], "max_files": 20})
        return

    conv_req = {
        "plan_path": plan["plan_path"],
        "write": True,
        "force": True,
    }
    if max_writes is not None:
        conv_req["max_writes"] = int(max_writes)
        conv_req["require_dry_run_if_over"] = threshold

    conv = _post(f"{base}/audit/js/convert", conv_req)
    print(f"[agent] convert: tried={conv['tried']} wrote={conv['wrote']} root={conv['root']}")

    if commit:
        _ = _post(f"{base}/audit/js/commit", {"plan_path": plan["plan_path"], "batch_size": 200})
        print("[agent] commit: done")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--port", type=int, default=8010)
    ap.add_argument("--md", nargs="*", default=[
        r"C:\CFH\TruthSource\docs\file_scan_results_js_v1.md",
        r"C:\CFH\TruthSource\docs\file_scan_results_jsx_v1.md",
        r"C:\CFH\TruthSource\docs\file_scan_results_ts_v1.md",
        r"C:\CFH\TruthSource\docs\file_scan_results_tsx_v1.md",
    ])
    ap.add_argument("--min-size", type=int, default=0)
    ap.add_argument("--exclude-rx", default="")
    ap.add_argument("--same-dir-only", action="store_true")
    ap.add_argument("--threshold", type=int, default=1200, help="if candidates exceed this, require dry-run")
    ap.add_argument("--max-writes", type=int, default=None, help="cap on successful writes per run")
    ap.add_argument("--commit", action="store_true")
    args = ap.parse_args()

    run(
        root=args.root,
        port=args.port,
        md_paths=args.md,
        size_min_bytes=args.min_size,
        exclude_regex=args.exclude_rx or None,
        same_dir_only=args.same_dir_only,
        threshold=args.threshold,
        max_writes=args.max_writes,
        commit=args.commit,
    )


if __name__ == "__main__":
    main()
