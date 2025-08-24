"""
Path: app/api/routes.py
Orchestrator API + provider mgmt; optional harvester + JS auditor + metrics + guardrails.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.orchestrator import Orchestrator

# Optional modules â€” routes remain available even if these are missing
try:
    from core.harvester import Harvester  # type: ignore
except Exception:  # pragma: no cover
    Harvester = None  # type: ignore
try:
    from core.js_auditor import JSAuditor  # type: ignore
except Exception:  # pragma: no cover
    JSAuditor = None  # type: ignore
try:
    from core.git_ops import GitOps  # type: ignore
except Exception:  # pragma: no cover
    GitOps = None  # type: ignore
try:
    from core.metrics import append_jsonl, ConvertEvent, ConvertSummary  # type: ignore
except Exception:  # pragma: no cover
    append_jsonl = None  # type: ignore
    ConvertEvent = None  # type: ignore
    ConvertSummary = None  # type: ignore

router = APIRouter()
orc = Orchestrator()

# ---------------- helpers ----------------
def _latest_artifact(stage: str) -> Optional[Path]:
    base = orc.config.base_dir
    if not base.exists():
        return None
    files = sorted(base.glob(f"{stage}_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None

def _in_root(p: Path, root: Path) -> bool:
    """True if p is within root (Windows-friendly)."""
    try:
        return p.resolve().is_relative_to(root.resolve())  # py>=3.9
    except Exception:  # fallback
        import os.path as _op
        return _op.normcase(str(p.resolve())).startswith(_op.normcase(str(root.resolve())))

def _metrics_path() -> Path:
    return orc.config.base_dir / "audit_metrics.jsonl"

# ---------------- orchestrator ----------------
@router.get("/orchestrator/status")
async def status() -> Dict[str, object]:
    return {"status": "ready", "completed": orc.get_completed_stages(), "run_id": orc.get_run_id()}

@router.post("/orchestrator/run-all")
async def run_all() -> Dict[str, object]:
    return orc.run_all()

@router.post("/orchestrator/run-stage/{stage}")
async def run_stage(stage: str) -> Dict[str, object]:
    try:
        return orc.run_stage(stage)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/orchestrator/artifacts/{stage}")
async def artifact(stage: str) -> Dict[str, object]:
    p = _latest_artifact(stage)
    if not p:
        raise HTTPException(status_code=404, detail="No artifacts for this stage")
    return {"artifact_file": str(p), "content": p.read_text(encoding="utf-8-sig")}

# ---------------- debug: settings/provider ----------------
@router.get("/debug/settings")
async def debug_settings() -> Dict[str, object]:
    s = getattr(orc, "settings", {})
    return {"pid": os.getpid(), "settings": {"DRY_RUN": s.get("DRY_RUN"), "PROVIDER": s.get("PROVIDER")}}

class ProviderUpdate(BaseModel):
    provider: str | None = None

@router.get("/debug/provider")
async def debug_provider_get() -> Dict[str, object]:
    orc._ensure_provider()
    prov = getattr(orc, "provider", None)
    return {
        "provider_loaded": prov is not None,
        "provider_class": (prov.__class__.__name__ if prov else None),
        "env": {"AIO_PROVIDER": os.getenv("AIO_PROVIDER"), "AIO_DRY_RUN": os.getenv("AIO_DRY_RUN")},
        "settings": getattr(orc, "settings", {}),
    }

@router.post("/debug/provider")
async def debug_provider_set(update: ProviderUpdate) -> Dict[str, object]:
    if update.provider:
        os.environ["AIO_PROVIDER"] = update.provider
    else:
        os.environ.pop("AIO_PROVIDER", None)
    orc._ensure_provider()
    prov = getattr(orc, "provider", None)
    return {
        "provider_loaded": prov is not None,
        "provider_class": (prov.__class__.__name__ if prov else None),
        "env": {"AIO_PROVIDER": os.getenv("AIO_PROVIDER"), "AIO_DRY_RUN": os.getenv("AIO_DRY_RUN")},
        "settings": getattr(orc, "settings", {}),
    }

# ---------------- harvest (optional) ----------------
class HarvestRun(BaseModel):
    root: str = "."
    limit: int = 20

@router.post("/harvest/run")
async def harvest_run(cfg: HarvestRun) -> Dict[str, object]:
    if Harvester is None:  # pragma: no cover
        raise HTTPException(status_code=503, detail="Harvester unavailable")
    hv = Harvester(Path(cfg.root))  # type: ignore
    items = hv.scan()
    summary = hv.summarize(items)
    bundle = hv.bundle(items, limit=cfg.limit)
    art_path = orc._write_artifact("harvest", summary)
    bundle_path = orc.config.base_dir / (Path(art_path).stem + "_bundle.py")
    bundle_path.write_text(bundle, encoding="utf-8")
    return {"count": len(items), "artifact": str(art_path), "bundle": str(bundle_path)}

@router.get("/harvest/report")
async def harvest_report() -> Dict[str, object]:
    p = _latest_artifact("harvest")
    if not p:
        raise HTTPException(status_code=404, detail="No harvest artifacts yet")
    b = p.with_name(p.stem + "_bundle.py")
    head = p.read_text(encoding="utf-8-sig").splitlines()[:20]
    bundle_head = b.read_text(encoding="utf-8").splitlines()[:30] if b.exists() else []
    return {"artifact": str(p), "bundle": (str(b) if b.exists() else None), "summary_head": head, "bundle_head": bundle_head}

# ---------------- JS/TS auditor (optional) ----------------
class AuditPlanReq(BaseModel):
    md_paths: List[str]
    workspace_root: Optional[str] = None
    size_min_bytes: int = 0
    exclude_regex: Optional[str] = None
    same_dir_only: bool = False

@router.post("/audit/js/plan")
async def audit_js_plan(req: AuditPlanReq) -> Dict[str, object]:
    if JSAuditor is None:  # pragma: no cover
        raise HTTPException(status_code=503, detail="JSAuditor unavailable")
    auditor = JSAuditor()  # type: ignore
    entries = auditor.parse_md_files(req.md_paths)  # type: ignore
    plan = auditor.plan(  # type: ignore
        entries,
        size_min_bytes=req.size_min_bytes,
        exclude_regex=req.exclude_regex,
        same_dir_only=req.same_dir_only,
    )
    if req.workspace_root:
        plan["workspace_root"] = req.workspace_root
        root = Path(req.workspace_root)
        in_root = [p for p in plan.get("convert_candidates", []) if _in_root(Path(p), root)]
        plan["convert_candidates_in_root"] = in_root
        plan.setdefault("counts", {})["convert_in_root"] = len(in_root)
    # JSON artifact
    art_json = orc._write_artifact("audit_js", json.dumps(plan, indent=2))
    # CSV artifact
    csv_lines = ["path,action"]
    csv_lines += [f"{p},keep_ts_tsx" for p in plan.get("keep_ts_tsx", [])]
    csv_lines += [f"{p},drop_js_already_converted" for p in plan.get("drop_js_already_converted", [])]
    csv_lines += [f"{p},convert_candidate" for p in plan.get("convert_candidates_in_root", plan.get("convert_candidates", []))]
    art_csv = Path(art_json).with_suffix(".csv")
    art_csv.write_text("\n".join(csv_lines), encoding="utf-8")
    return {"counts": plan.get("counts", {}), "plan_path": str(art_json), "csv_path": str(art_csv)}

class AuditConvertReq(BaseModel):
    plan_path: str
    write: bool = True
    force: bool = True
    root_override: Optional[str] = None
    # Guardrails (all optional, backward compatible):
    #  - if max_writes is set, stop after that many successful writes
    #  - if require_dry_run_if_over is set and candidates exceed it, reject unless write=False
    max_writes: Optional[int] = None
    require_dry_run_if_over: Optional[int] = None
    quarantine_failed: bool = True  # only used if you later wire quarantine logic

@router.post("/audit/js/convert")
async def audit_js_convert(req: AuditConvertReq) -> Dict[str, object]:
    p = Path(req.plan_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="plan not found")
    plan = json.loads(p.read_text(encoding="utf-8-sig"))
    candidates: List[str] = plan.get("convert_candidates_in_root") or plan.get("convert_candidates", [])
    root = Path(req.root_override or plan.get("workspace_root") or Path.cwd())

    # guard: large runs require dry-run unless explicitly allowed
    if req.require_dry_run_if_over and len(candidates) > req.require_dry_run_if_over and req.write:
        raise HTTPException(
            status_code=400,
            detail=f"Too many candidates ({len(candidates)}). Set write=false or raise require_dry_run_if_over threshold."
        )

    wrote = 0
    tried = 0
    missing = 0
    outside = 0
    quarantined = 0
    outs: List[Dict[str, object]] = []

    for s in candidates:
        if req.max_writes is not None and wrote >= req.max_writes:
            break
        tried += 1
        sp = Path(s)

        if not sp.exists():
            missing += 1
            outs.append({"src": s, "ok": False, "reason": "missing"})
            if append_jsonl and ConvertEvent:
                append_jsonl(_metrics_path(), ConvertEvent("file", s, False, "missing", None, str(root), orc.get_run_id()).to_dict())
            continue

        if not _in_root(sp, root):
            outside += 1
            outs.append({"src": s, "ok": False, "reason": "outside_root"})
            if append_jsonl and ConvertEvent:
                append_jsonl(_metrics_path(), ConvertEvent("file", s, False, "outside_root", None, str(root), orc.get_run_id()).to_dict())
            continue

        res = orc.convert_file(sp, write_to_repo=req.write, include_tests=True, force_write=req.force)
        ok = bool(res.get("ts_path"))
        wrote += 1 if ok else 0
        outs.append({"src": s, **res})

        if append_jsonl and ConvertEvent:
            append_jsonl(_metrics_path(), ConvertEvent("file", s, ok, None if ok else "unknown", res.get("ts_path"), str(root), orc.get_run_id()).to_dict())

    if append_jsonl and ConvertSummary:
        append_jsonl(
            _metrics_path(),
            ConvertSummary("summary", tried, wrote, outside, missing, quarantined, str(root), orc.get_run_id()).to_dict(),
        )

    return {"tried": tried, "wrote": wrote, "results": outs, "root": str(root)}

# ---------- dry-run & commit ----------
class AuditDryRunReq(BaseModel):
    plan_path: str
    max_files: int = 20
    root_override: Optional[str] = None

@router.post("/audit/js/dry-run")
async def audit_js_dry_run(req: AuditDryRunReq) -> Dict[str, object]:
    p = Path(req.plan_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="plan not found")
    plan = json.loads(p.read_text(encoding="utf-8-sig"))
    candidates: List[str] = plan.get("convert_candidates_in_root") or plan.get("convert_candidates", [])
    root = Path(req.root_override or plan.get("workspace_root") or Path.cwd())
    tried = 0
    outs: List[Dict[str, object]] = []
    for s in candidates:
        if tried >= max(1, req.max_files):
            break
        sp = Path(s)
        if not sp.exists() or not _in_root(sp, root):
            continue
        ts = sp.with_suffix(".tsx" if sp.suffix.lower() == ".jsx" else ".ts")
        outs.append({"src": str(sp), "ts_target": str(ts), "would_write": True})
        tried += 1
    art = orc._write_artifact("audit_js_dryrun", json.dumps(outs, indent=2))
    return {"preview_count": len(outs), "preview_path": str(art), "root": str(root)}

class AuditCommitReq(BaseModel):
    plan_path: str
    root_override: Optional[str] = None
    batch_size: int = 100
    dry_run: bool = False

@router.post("/audit/js/commit")
async def audit_js_commit(req: AuditCommitReq) -> Dict[str, object]:
    if GitOps is None:  # pragma: no cover
        raise HTTPException(status_code=503, detail="GitOps unavailable")
    p = Path(req.plan_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="plan not found")
    plan = json.loads(p.read_text(encoding="utf-8-sig"))
    root = Path(req.root_override or plan.get("workspace_root") or Path.cwd())
    cands: List[str] = plan.get("convert_candidates_in_root") or plan.get("convert_candidates", [])
    ts_files: List[Path] = []
    for s in cands:
        sp = Path(s)
        if not _in_root(sp, root):
            continue
        ts = sp.with_suffix(".tsx" if sp.suffix.lower() == ".jsx" else ".ts")
        if ts.exists():
            ts_files.append(ts)
    if req.dry_run:
        return {"root": str(root), "ts_existing": len(ts_files), "dry_run": True}
    ops = GitOps(root)  # type: ignore
    commits = ops.add_and_commit(ts_files, batch_size=req.batch_size)  # type: ignore
    return {"root": str(root), "ts_existing": len(ts_files), "commits": commits, "dry_run": False}

