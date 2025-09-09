# ==== 0) AIO-CLI | STANDARD FILE HEADER — START ==============================
# File: app/ops_cli.py
# Purpose:
#   Command-line entry for the orchestrator. Drives scanning, reviewing,
#   generating, and special pipelines backed by app/ops.py.
#
# Public Commands:
#   - scan                : discover candidates and write grouped file
#   - review|generate|persist|run-batch
#   - ai-check            : print provider key presence (no network calls)
#   - scan-special        : multi-root scan for tests / letters-only
#   - run-special         : scan + process special set (review/generate/all)
#
# Key Outputs (relative to repo root):
#   - reports/grouped_files.txt
#   - reports/review_multi_<run_id>.json
#   - reports/_last_review.txt               (pointer written explicitly)
#   - reports/special_scan_<run_id>.json
#   - reports/special_inventory_<run_id>.csv
#   - reports/review_summary_special_<run_id>.json
#   - reports/gates_<run_id>.json
#
# Notes:
#   - CLI prefers process_batch_ext (if present) but falls back to process_batch.
#   - After batch run, we explicitly write _last_review.txt -> review_multi_<run_id>.json
#   - Optional GitHub upload is handled inside ops.py when AIO_UPLOAD_TS=1.
#
# SPDX-License-Identifier: MIT
# Last-Updated: 2025-09-08
# ==== 0) AIO-CLI | STANDARD FILE HEADER — END ================================


# ==== 1) AIO-CLI | IMPORTS — START ==========================================
from __future__ import annotations

from pathlib import Path
import argparse
import json
import os
import uuid
import inspect
from typing import Optional, List, Tuple, Any

# optional .env autoload (safe even if .env is missing)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from app.ops import (
    fetch_candidates, process_batch,
    scan_special, process_special,
    write_grouped_files, filter_cryptic,   # helper utilities in app.ops
)

# Optional/advanced helpers — fall back gracefully if not available
try:
    from app.ops import process_batch_ext, run_gates, upload_generated_to_github  # type: ignore
except Exception:
    process_batch_ext = None  # type: ignore

    def run_gates(run_id: str):  # type: ignore
        return None

    upload_generated_to_github = None  # type: ignore
# ==== 1) AIO-CLI | IMPORTS — END ============================================


# ==== 2) AIO-CLI | HELPERS — START ==========================================
def _split_csv(s: Optional[str]) -> Optional[List[str]]:
    return [b.strip() for b in s.replace(";", ",").split(",")] if s else None

def _flex_call(fn, **kwargs):
    """Call fn with only the kwargs it supports. Also remap common param aliases."""
    sig = inspect.signature(fn)
    params = set(sig.parameters.keys())

    # Common alias: bundle_by_src -> bundles
    if "bundle_by_src" in kwargs and "bundle_by_src" not in params and "bundles" in params:
        kwargs = dict(kwargs)
        kwargs["bundles"] = kwargs.pop("bundle_by_src")

    filtered = {k: v for k, v in kwargs.items() if k in params}
    return fn(**filtered)

def _fetch_candidates_safe(**kwargs) -> Tuple[Any, Any, Any]:
    """Always return (cands, bundles, repos) even if underlying fn returns fewer."""
    res = _flex_call(fetch_candidates, **kwargs)
    if isinstance(res, tuple):
        if len(res) == 3:
            return res
        if len(res) == 2:
            cands, bundles = res
            return cands, bundles, None
        if len(res) == 1:
            return res[0], {}, None
    # Unknown shape; best-effort
    return res, {}, None

def _process_batch_safe(runner, **kwargs):
    """Call process_batch(_ext) with filtered kwargs; always return a list-ish result."""
    res = _flex_call(runner, **kwargs)
    if res is None:
        return []
    return res

def _ensure_reports_dir() -> Path:
    p = Path("reports")
    p.mkdir(parents=True, exist_ok=True)
    return p

def _latest_report(prefix: str) -> Optional[Path]:
    rpt = _ensure_reports_dir()
    files = sorted(rpt.glob(f"{prefix}_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
    return files[0] if files else None

def _write_pointer(pointer_name: str, target: Optional[Path]) -> Optional[Path]:
    """Write a small text file in reports/ that points at another report file."""
    if not target:
        return None
    rpt = _ensure_reports_dir()
    ptr = rpt / pointer_name
    try:
        ptr.write_text(str(target), encoding="utf-8")
        return ptr
    except Exception:
        return None
# ==== 2) AIO-CLI | HELPERS — END ============================================


# ==== 3) AIO-CLI | MAIN — START =============================================
def main():
    ap = argparse.ArgumentParser(prog="ai-orchestrator", description="Scan and batch-process repo files")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # ---- standard scan/review/generate/persist/run-batch ---------------------
    sc = sub.add_parser("scan", help="Scan repo and write reports/scan_*.json + inventory csv")
    sc.add_argument("--user", default="carfinancinghub")
    sc.add_argument("--org", default=None)
    sc.add_argument("--repo-name", default=None)
    sc.add_argument("--platform", default="github", choices=["github", "gitlab", "local"])
    sc.add_argument("--branches", default="main")

    rb = sub.add_parser("review", help="Review a batch of files")
    rb.add_argument("--limit", type=int, default=50)
    rb.add_argument("--out", default="artifacts")

    gb = sub.add_parser("generate", help="Generate a batch of files")
    gb.add_argument("--limit", type=int, default=50)
    gb.add_argument("--out", default="artifacts")

    pb = sub.add_parser("persist", help="Persist a batch of files")
    pb.add_argument("--limit", type=int, default=50)
    pb.add_argument("--out", default="artifacts")

    ab = sub.add_parser("run-batch", help="scan -> review -> generate -> persist in one pass")
    ab.add_argument("--mode", default="all", choices=["all", "review", "generate", "persist"])
    ab.add_argument("--limit", type=int, default=50)
    ab.add_argument("--out", default="artifacts")

    # ---- provider sanity -----------------------------------------------------
    sub.add_parser("ai-check", help="Verify provider keys presence (no network calls)")

    # ---- SPECIAL: multi-root scan / process ---------------------------------
    sp = sub.add_parser("scan-special", help="Scan multiple roots for test files and letters-only basenames")
    sp.add_argument("--roots", default=os.getenv("AIO_SCAN_ROOTS", os.getenv("AIO_REPO_ROOT", str(Path.cwd()))))
    sp.add_argument("--exts", default=os.getenv("AIO_SPECIAL_EXTS", "js,jsx,ts,tsx,md"))
    sp.add_argument("--skip-dirs", default=os.getenv("AIO_SKIP_DIRS", ""))
    sp.add_argument("--only-tests", action="store_true", help="Limit to *.test.* files")
    sp.add_argument("--only-letters", action="store_true", help="Limit to filenames with letters only (A-Za-z)")

    rp = sub.add_parser("run-special", help="Scan + review/generate/persist special files")
    rp.add_argument("--mode", default="review", choices=["review", "generate", "persist", "all"])
    rp.add_argument("--limit", type=int, default=100)
    rp.add_argument("--roots", default=os.getenv("AIO_SCAN_ROOTS", os.getenv("AIO_REPO_ROOT", str(Path.cwd()))))
    rp.add_argument("--exts", default=os.getenv("AIO_SPECIAL_EXTS", "js,jsx,ts,tsx,md"))
    rp.add_argument("--skip-dirs", default=os.getenv("AIO_SKIP_DIRS", ""))
    rp.add_argument("--only-tests", action="store_true")
    rp.add_argument("--only-letters", action="store_true")

    # ----------[ Commands ]---------------
    args = ap.parse_args()
    run_id = uuid.uuid4().hex[:8]

    if args.cmd == "ai-check":
        payload = {
            "OPENAI_API_KEY": "set" if os.getenv("OPENAI_API_KEY") else "missing",
            "GEMINI_API_KEY": "set" if os.getenv("GEMINI_API_KEY") else "missing",
            "GROK_API_KEY": "set" if os.getenv("GROK_API_KEY") else "missing",
            "AIO_DRY_RUN": os.getenv("AIO_DRY_RUN", "true"),
        }
        print(json.dumps(payload, indent=2))
        return

    if args.cmd == "scan":
        cands, bundles, repos = _fetch_candidates_safe(
            org=args.org, user=None, repo_name=args.repo_name,
            platform=args.platform, token=None, run_id=run_id,
            branches=_split_csv(getattr(args, "branches", None)), local_inventory_paths=None
        )
        # NEW: filter noisy names and drop a grouping file for SG Man
        grouped_path = None
        try:
            cands = filter_cryptic(cands)
            write_grouped_files(cands, out_path="reports/grouped_files.txt")
            grouped_path = "reports/grouped_files.txt"
        except Exception:
            pass

        print(json.dumps({
            "ok": True,
            "run_id": run_id,
            "candidates": len(cands) if cands is not None else 0,
            "grouped": grouped_path
        }))
        return

    if args.cmd in {"review", "generate", "persist", "run-batch"}:
        # re-scan to get the candidate slice (keeps behavior you had before)
        cands, bundles, repos = _fetch_candidates_safe(
            org=None, user=None, repo_name=None, platform="local", token=None, run_id=run_id,
            branches=["main"], local_inventory_paths=None
        )
        # Parity with scan
        try:
            cands = filter_cryptic(cands)
            write_grouped_files(cands, out_path="reports/grouped_files.txt")
        except Exception:
            pass

        # honor --mode passed to run-batch; fall back to default behavior
        mode = (getattr(args, "mode", None) or ("all" if args.cmd == "run-batch" else args.cmd))

        runner = process_batch_ext or process_batch  # prefer extended if available

        res = _process_batch_safe(
            runner,
            platform="local", token=None, candidates=cands, bundle_by_src=bundles,
            run_id=run_id, batch_offset=0, batch_limit=args.limit, mode=mode
        )

        # pointer to the review file (created by process_batch_ext)
        try:
            (Path("reports") / "_last_review.txt").write_text(
                f"reports/review_multi_{run_id}.json", encoding="utf-8"
            )
        except Exception:
            pass

        if mode in {"persist", "all"}:
            gates_path = run_gates(run_id) if callable(run_gates) else None  # type: ignore
            print(json.dumps({
                "ok": True, "run_id": run_id, "processed": len(res) if res is not None else 0,
                "mode": mode, "gates": gates_path
            }))
            return

        print(json.dumps({"ok": True, "run_id": run_id, "processed": len(res) if res is not None else 0, "mode": mode}))
        return

    if args.cmd == "scan-special":
        roots = _split_csv(args.roots) or []
        exts = _split_csv(args.exts) or ["js", "jsx", "ts", "tsx", "md"]
        skip_dirs = _split_csv(args.skip_dirs) or []
        items = scan_special(roots=roots, exts=exts, extra_skips=skip_dirs, run_id=run_id)
        if args.only_tests:
            items = [it for it in items if it.get("category") == "test"]
        if args.only_letters:
            items = [it for it in items if it.get("category") == "letters_only"]
        print(json.dumps({"ok": True, "run_id": run_id, "items": len(items)}))
        return

    if args.cmd == "run-special":
        roots = _split_csv(args.roots) or []
        exts = _split_csv(args.exts) or ["js", "jsx", "ts", "tsx", "md"]
        skip_dirs = _split_csv(args.skip_dirs) or []
        items = scan_special(roots=roots, exts=exts, extra_skips=skip_dirs, run_id=run_id)
        if args.only_tests:
            items = [it for it in items if it.get("category") == "test"]
        if args.only_letters:
            items = [it for it in items if it.get("category") == "letters_only"]
        res = process_special(items=items, run_id=run_id, limit=args.limit, mode=args.mode)
        print(json.dumps({"ok": True, "run_id": run_id, "processed": len(res), "mode": args.mode}))
        return
# ==== 3) AIO-CLI | MAIN — END ===============================================


# ==== 4) AIO-CLI | ENTRYPOINT — START =======================================
if __name__ == "__main__":
    main()
# ==== 4) AIO-CLI | ENTRYPOINT — END =========================================
