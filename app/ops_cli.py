# Path: app/ops_cli.py
from __future__ import annotations
import argparse, json, os, uuid
from typing import Optional, List
from app.ops import fetch_candidates, process_batch

def _split(s: Optional[str]) -> Optional[List[str]]:
    return [b.strip() for b in s.split(",")] if s else None

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sc = sub.add_parser("scan")
    sc.add_argument("--user", default="carfinancinghub")
    sc.add_argument("--org", default=None)
    sc.add_argument("--repo-name", default=None)
    sc.add_argument("--platform", default="github", choices=["github","gitlab"])
    sc.add_argument("--branches", default="main")

    rb = sub.add_parser("run-batch")
    rb.add_argument("--user", default="carfinancinghub")
    rb.add_argument("--org", default=None)
    rb.add_argument("--repo-name", default=None)
    rb.add_argument("--platform", default="github", choices=["github","gitlab"])
    rb.add_argument("--branches", default="main")
    rb.add_argument("--offset", type=int, default=0)
    rb.add_argument("--limit", type=int, default=100)

    args = ap.parse_args()
    token = os.getenv("GITHUB_TOKEN") if args.platform == "github" else os.getenv("GITLAB_TOKEN")
    run_id = uuid.uuid4().hex[:8]

    if args.cmd == "scan":
        cands, bundles, repos = fetch_candidates(
            org=args.org, user=args.user, repo_name=args.repo_name,
            platform=args.platform, token=token, run_id=run_id,
            branches=_split(args.branches), local_inventory_paths=None
        )
        print(json.dumps({"ok": True, "run_id": run_id, "candidates": len(cands)}))
        return

    if args.cmd == "run-batch":
        cands, bundles, repos = fetch_candidates(
            org=args.org, user=args.user, repo_name=args.repo_name,
            platform=args.platform, token=token, run_id=run_id,
            branches=_split(args.branches), local_inventory_paths=None
        )
        res = process_batch(
            platform=args.platform, token=token,
            candidates=cands, bundle_by_src=bundles, run_id=run_id,
            batch_offset=args.offset, batch_limit=args.limit,
        )
        print(json.dumps({"ok": True, "run_id": run_id, "processed": len(res)}))

if __name__ == "__main__":
    main()
