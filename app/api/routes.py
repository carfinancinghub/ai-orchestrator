"""
Orchestrator API + provider mgmt; optional harvester + JS auditor + quarantine tools.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.orchestrator import Orchestrator

# Optional modules — routes remain available even if these are missing
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
    except Exception:
        import os.path as _op
        return _op.normcase(str(p.resolve())).startswith(_op.normcase(str(root.resolve())))

def _quarantine_file(src: Path, reason: str, qroot: Optional[Path] = None) -> Optional[str]:
    """
    Move a problematic source file into artifacts/quarantine/YYYYMMDD/<reason>/filename
    and append a line to artifacts/quarantine_manifest.jsonl for later restoration.
    Returns dest path (string) or None if src missing.
    """
    if not src.exists():
        return None
    qroot = qroot or (orc.config.base_dir / "quarantine")
    day = datetime.utcnow().strftime("%Y%m%d")
    dest_dir = qroot / day / reason
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name

    # Avoid collisions
    i = 1
    while dest.exists():
        dest = dest_dir / f"{src.stem}_{i}{src.suffix}"
        i += 1

    shutil.move(str(src), str(dest))

    manifest = orc.config.base_dir / "quarantine_manifest.jsonl"
    rec = {
        "when_utc": datetime.utcnow().isoformat(),
        "src": str(src),
        "dest": str(dest),
        "reason": reason,
    }
    with manifest.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return str(dest)

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
    return {"artifact_file": str(p), "content": p.read_text(encoding="utf-8")}

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
    head = p.read_text(encoding="utf-8").splitlines()[:20]
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
    quarantine_failed: bool = True  # NEW: move problematic files for manual review

@router.post("/audit/js/convert")
async def audit_js_convert(req: AuditConvertReq) -> Dict[str, object]:
    p = Path(req.plan_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="plan not found")
    plan = json.loads(p.read_text(encoding="utf-8"))
    candidates: List[str] = plan.get("convert_candidates_in_root") or plan.get("convert_candidates", [])
    root = Path(req.root_override or plan.get("workspace_root") or Path.cwd())
    wrote = 0
    tried = 0
    outs: List[Dict[str, object]] = []
    for s in candidates:
        tried += 1
        sp = Path(s)
        if not sp.exists():
            qdest = _quarantine_file(sp, "missing") if req.quarantine_failed else None
            outs.append({"src": s, "ok": False, "reason": "missing", "quarantined_to": qdest})
            continue
        if not _in_root(sp, root):
            qdest = _quarantine_file(sp, "outside_root") if req.quarantine_failed else None
            outs.append({"src": s, "ok": False, "reason": "outside_root", "quarantined_to": qdest})
            continue
        res = orc.convert_file(sp, write_to_repo=req.write, include_tests=True, force_write=req.force)
        ok = bool(res.get("ts_path"))
        if not ok and req.quarantine_failed:
            qdest = _quarantine_file(sp, "conversion_failed")
            outs.append({"src": s, "ok": False, "reason": "conversion_failed", "quarantined_to": qdest, **res})
            continue
        wrote += 1 if ok else 0
        outs.append({"src": s, **res, "ok": ok})
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
    plan = json.loads(p.read_text(encoding="utf-8"))
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
    plan = json.loads(p.read_text(encoding="utf-8"))
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

# ---------- quarantine: list & restore ----------

@router.get("/audit/js/quarantine/list")
async def audit_quarantine_list(limit: int = 200) -> Dict[str, object]:
    """Return recent quarantine manifest entries (newest first)."""
    manifest = orc.config.base_dir / "quarantine_manifest.jsonl"
    if not manifest.exists():
        return {"count": 0, "items": []}
    lines = manifest.read_text(encoding="utf-8").splitlines()
    items = [json.loads(x) for x in lines if x.strip()]
    items.sort(key=lambda r: r.get("when_utc", ""), reverse=True)
    return {"count": len(items), "items": items[: max(1, limit)]}

class QuarantineRestoreReq(BaseModel):
    dest_paths: List[str]  # paths inside quarantine to restore
    overwrite: bool = False

@router.post("/audit/js/quarantine/restore")
async def audit_quarantine_restore(req: QuarantineRestoreReq) -> Dict[str, object]:
    """
    Best-effort restore: for each manifest entry whose 'dest' is in dest_paths,
    move file back to recorded 'src' if possible.
    """
    manifest = orc.config.base_dir / "quarantine_manifest.jsonl"
    if not manifest.exists():
        raise HTTPException(status_code=404, detail="manifest not found")
    lines = manifest.read_text(encoding="utf-8").splitlines()
    items = [json.loads(x) for x in lines if x.strip()]
    by_dest = {i["dest"]: i for i in items if "dest" in i and "src" in i}
    restored = []
    skipped = []
    for target in req.dest_paths:
        rec = by_dest.get(target)
        if not rec:
            skipped.append({"dest": target, "reason": "not_in_manifest"})
            continue
        src = Path(rec["src"])
        dest = Path(rec["dest"])
        if not dest.exists():
            skipped.append({"dest": target, "reason": "missing_quarantine_file"})
            continue
        src.parent.mkdir(parents=True, exist_ok=True)
        if src.exists() and not req.overwrite:
            skipped.append({"dest": target, "reason": "src_exists"})
            continue
        shutil.move(str(dest), str(src))
        restored.append({"dest": target, "restored_to": str(src)})
    return {"restored": restored, "skipped": skipped}
