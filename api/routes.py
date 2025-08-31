# Path: C:\c\ai-orchestrator\api\routes.py
# Version: 0.2.0
# Last Updated: 2025-08-30 20:52 PDT
# Purpose: API routes for CFH AI-Orchestrator to handle migration requests
from __future__ import annotations
from fastapi import APIRouter, Body, Query
from typing import Optional, Dict
import os, uuid
from app.ops import fetch_candidates, process_batch

router = APIRouter()

@router.get("/health", operation_id="router_health")
def health():
    return {"ok": True}

@router.post("/run-one")
def run_one(
    body: Optional[Dict] = Body(default=None),
    prompt_key: Optional[str] = Query(default=None),
    tier: str = Query(default="free"),
    root: Optional[str] = Query(default=None),
    org: Optional[str] = Query(default=None),
    user: Optional[str] = Query(default=None),
    repo_name: Optional[str] = Query(default=None),
    platform: str = Query(default="github"),
    branches: str = Query(default="main"),
    batch_offset: int = Query(default=0),
    batch_limit: int = Query(default=100),
):
    params = dict(body or {})
    for k, v in {
        "prompt_key": prompt_key, "tier": tier, "root": root,
        "user": user, "org": org, "repo_name": repo_name,
        "platform": platform, "branches": branches,
        "batch_offset": batch_offset, "batch_limit": batch_limit,
    }.items():
        if k not in params or params[k] in (None, ""):
            params[k] = v
    account = params.get("user") or params.get("org") or ""
    run_id = uuid.uuid4().hex[:8]
    token = os.getenv("GITHUB_TOKEN") if params["platform"] == "github" else os.getenv("GITLAB_TOKEN")
    cands, bundles, repos = fetch_candidates(
        org=None, user=account, repo_name=params.get("repo_name"),
        platform=params["platform"], token=token, run_id=run_id,
        branches=[b.strip() for b in (params.get("branches") or "main").split(",")],
        local_inventory_paths=[params.get("root")] if params.get("root") else None,
    )
    if params.get("prompt_key") == "convert" and params.get("tier") == "wow":
        res = process_batch(
            platform=params["platform"], token=token,
            candidates=cands, bundle_by_src=bundles, run_id=run_id,
            batch_offset=int(params.get("batch_offset") or 0),
            batch_limit=int(params.get("batch_limit") or 100),
        )
        return {"ok": True, "run_id": run_id, "processed": len(res)}
    return {"ok": True, "run_id": run_id, "candidates": len(cands)}