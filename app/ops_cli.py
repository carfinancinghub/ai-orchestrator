# ============================================================
# File: app/ops_cli.py
# Purpose: Command-line entry for orchestrator (standard + special)
# ============================================================
from __future__ import annotations
from pathlib import Path
import argparse
import json
import os
import uuid
from typing import Optional, List
 

# optional .env autoload (safe even if .env is missing)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from app.ops import (
    fetch_candidates, process_batch,
    scan_special, process_special,
)


def _split_csv(s: Optional[str]) -> Optional[List[str]]:
    return [b.strip() for b in s.replace(";", ",").split(",")] if s else None


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
    ai = sub.add_parser("ai-check", help="Verify provider keys presence (no network calls)")

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

    args = ap.parse_args()

    if args.cmd == "ai-check":
        payload = {
            "OPENAI_API_KEY": "set" if os.getenv("OPENAI_API_KEY") else "missing",
            "GEMINI_API_KEY": "set" if os.getenv("GEMINI_API_KEY") else "missing",
            "GROK_API_KEY": "set" if os.getenv("GROK_API_KEY") else "missing",
            "AIO_DRY_RUN": os.getenv("AIO_DRY_RUN", "true"),
        }
        print(json.dumps(payload, indent=2))
        return


    run_id = uuid.uuid4().hex[:8]

    if args.cmd == "scan":
        cands, bundles, repos = fetch_candidates(
            org=args.org, user=None, repo_name=args.repo_name,
            platform=args.platform, token=None, run_id=run_id,
            branches=_split_csv(getattr(args, "branches", None)), local_inventory_paths=None
        )
        print(json.dumps({"ok": True, "run_id": run_id, "candidates": len(cands)}))
        return

    if args.cmd in {"review", "generate", "persist", "run-batch"}:
        # re-scan to get the candidate slice (keeps behavior you had before)
        cands, bundles, repos = fetch_candidates(
            org=None, user=None, repo_name=None, platform="local", token=None, run_id=run_id,
            branches=["main"], local_inventory_paths=None
        )
        mode = "all" if args.cmd == "run-batch" else args.cmd
        res = process_batch(
            platform="local", token=None, candidates=cands, bundle_by_src=bundles,
            run_id=run_id, batch_offset=0, batch_limit=args.limit, mode=mode
        )
        print(json.dumps({"ok": True, "run_id": run_id, "processed": len(res), "mode": mode}))
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


if __name__ == "__main__":
    main()
