# api/routes.py
from __future__ import annotations

import csv
import hashlib
import json as _json_mod
import os
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, List, Optional, Tuple

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
FRONTEND_ROOT = Path(os.getenv("FRONTEND_ROOT", r"C:\CFH\frontend")).resolve()
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "reports")).resolve()
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# single router (meta routes are defined in app/server.py)
router = APIRouter(tags=["convert"])

# -----------------------------------------------------------------------------
# Small helpers
# -----------------------------------------------------------------------------
def _sha1_file(p: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha1()
    try:
        with p.open("rb") as f:
            while True:
                b = f.read(chunk)
                if not b:
                    break
                h.update(b)
    except Exception:
        return ""
    return h.hexdigest()


def _iter_code_files(root: Path, exts: Tuple[str, ...] = (".ts", ".tsx", ".js", ".jsx")) -> Iterable[Path]:
    if not root.exists():
        return []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in exts:
            yield p


def _write_batches(rows: List[Dict[str, Any]], module: str, out_dir: Path, chunk_size: int = 100) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    outs: List[Path] = []
    if not rows:
        return outs
    # stable slices
    for i in range(0, len(rows), chunk_size):
        part = rows[i : i + chunk_size]
        idx = (i // chunk_size) + 1
        outp = out_dir / f"Batch_{module}_{idx}.csv"
        with outp.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["path", "size", "mtime", "sha1"])
            w.writeheader()
            w.writerows(part)
        outs.append(outp)
    return outs


def _collect_batch_rows(frontend_root: Path, module: str, min_size: int = 1) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for p in _iter_code_files(frontend_root):
        try:
            st = p.stat()
            if st.st_size < min_size:
                continue
            rows.append(
                {
                    "path": str(p),
                    "size": int(st.st_size),
                    "mtime": int(st.st_mtime),
                    "sha1": _sha1_file(p),
                }
            )
        except Exception:
            continue
    # keep deterministic
    rows.sort(key=lambda r: (r["path"].lower(), r["size"]))
    return rows


def _preview_text(path: str, max_lines: int = 60) -> List[str]:
    try:
        data = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
        return data[:max_lines]
    except Exception as e:
        return [f"/* preview error: {e!r} */"]


def _normalize_batch_artifacts(root_dir: Path, batch_obj: Dict[str, Any] | None) -> Dict[str, Any]:
    """
    Accepts a reviewer batch result and normalizes keys:
      returns { batch_md: str|None, per_file_mds: [str], dependencies: { file: [deps] } }
    """
    out: Dict[str, Any] = {"batch_md": None, "per_file_mds": [], "dependencies": {}}
    if not batch_obj:
        return out
    bm = batch_obj.get("batch_md")
    if isinstance(bm, str):
        out["batch_md"] = bm
    pmds = batch_obj.get("per_file_mds") or batch_obj.get("per_file_docs") or []
    if isinstance(pmds, list):
        out["per_file_mds"] = [str(x) for x in pmds]
    deps = batch_obj.get("deps_index") or batch_obj.get("dependencies") or {}
    if isinstance(deps, dict):
        out["dependencies"] = {str(k): list(v or []) for k, v in deps.items()}
    return out


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class PrepReq(BaseModel):
    module: str
    label: Optional[str] = None
    min_size: int = 1
    chunk_size: int = 100


class ConvertTreeReq(BaseModel):
    module: str
    root: Optional[str] = None


class BuildTsReq(BaseModel):
    module: Optional[str] = None
    md_paths: List[str]
    pruned_map: Optional[str] = None
    label: Optional[str] = None


class PruneReq(BaseModel):
    md_paths: List[str]
    strategy: str = "keep_all"
    out_csv: str = "reports/prune/pruned_module_map.csv"


# -----------------------------------------------------------------------------
# /convert/prep
# -----------------------------------------------------------------------------
@router.post("/convert/prep", name="convert_prep")
def convert_prep(req: PrepReq = Body(...)) -> dict:
    """
    Inventory code under FRONTEND_ROOT and write Batch_{module}_*.csv files
    to reports/batches. Returns list of batch CSV paths.
    """
    batch_dir = REPORTS_DIR / "batches"
    rows = _collect_batch_rows(FRONTEND_ROOT, req.module, min_size=req.min_size)
    outs = _write_batches(rows, req.module, batch_dir, chunk_size=req.chunk_size)
    return {
        "ok": True,
        "module": req.module,
        "count": len(rows),
        "batches": [p.as_posix() for p in outs],
    }


# -----------------------------------------------------------------------------
# /convert/tree  (light stub to keep parity)
# -----------------------------------------------------------------------------
@router.post("/convert/tree", name="convert_tree")
def convert_tree(req: ConvertTreeReq = Body(...)) -> dict:
    root = Path(req.root or FRONTEND_ROOT)
    if not root.exists():
        raise HTTPException(status_code=404, detail=f"root not found: {root}")
    total = sum(1 for _ in _iter_code_files(root))
    return {"ok": True, "module": req.module, "root": root.as_posix(), "count": int(total)}


# -----------------------------------------------------------------------------
# /build_ts
# -----------------------------------------------------------------------------
@router.post("/build_ts", name="build_ts")
def build_ts(req: BuildTsReq = Body(...)) -> dict:
    """
    Build TS/TSX files from a list of .plan.md (or per-file review .md) docs.
    - Returns { ok, written, errors, label, out_dir }
    - If app.prep.ts_builder.build_ts_from_plans exists, we call it; otherwise
      we fall back to a safe stub that writes .tsx stubs into src/_ai_out.
    """
    written: List[str] = []
    errors: List[str] = []
    label = req.label or (req.module or "build")

    # 1) try native builder if present
    used_native = False
    try:
        # Expected signature: build_ts_from_plans(md_paths, pruned_map, label) -> dict or list
        from app.prep.ts_builder import build_ts_from_plans  # type: ignore

        res = build_ts_from_plans(req.md_paths, req.pruned_map, label)
        if isinstance(res, list):
            written = [str(p) for p in res]
        elif isinstance(res, dict):
            written = [str(p) for p in (res.get("written") or [])]
            errors.extend([str(e) for e in (res.get("errors") or [])])
        else:
            errors.append("native builder returned unsupported type")
        used_native = True
    except Exception as e:
        # fallback below
        if os.getenv("ORCH_VERBOSE", "0") == "1":
            errors.append(f"native_builder_unavailable: {repr(e)}")

    # 2) fallback stub
    out_root = Path("src") / "_ai_out"
    out_root.mkdir(parents=True, exist_ok=True)
    if not used_native:
        for md in req.md_paths:
            try:
                mdp = Path(md)
                outp = out_root / mdp.name.replace(".md", ".tsx")
                header = (
                    f"/**\n"
                    f" * GENERATED STUB FROM PLAN\n"
                    f" * plan: {mdp.as_posix()}\n"
                    f" * date: {datetime.utcnow().isoformat()}Z\n"
                    f" */\n\n"
                )
                outp.write_text(header + "export default function TODO() { return null }\n", encoding="utf-8")
                written.append(outp.as_posix())
            except Exception as e:
                errors.append(f"{md}: {e!r}")

    return {"ok": True, "written": written, "errors": errors, "label": label, "out_dir": out_root.as_posix()}


# -----------------------------------------------------------------------------
# /prune
# -----------------------------------------------------------------------------
@router.post("/prune", name="prune")
def prune(req: PruneReq = Body(...)) -> dict:
    """
    Produce/overwrite pruned_module_map.csv with "keep_all" mapping for provided md_paths.
    CSV columns: source,action,reason
    """
    if req.strategy != "keep_all":
        raise HTTPException(status_code=400, detail="only strategy=keep_all is implemented here")

    out_csv = Path(req.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"source": str(p), "action": "keep", "reason": "keep_all"} for p in req.md_paths]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["source", "action", "reason"])
        w.writeheader()
        w.writerows(rows)
    return {"ok": True, "csv": out_csv.as_posix(), "count": len(rows)}


# -----------------------------------------------------------------------------
# /resolve_deps (canonical singleton)
# -----------------------------------------------------------------------------
class ResolveDepsReq(BaseModel):
    md_paths: List[str] = []
    tsconfig_path: Optional[str] = None      # default: tsconfig.json at repo root
    aliases: Optional[Dict[str, List[str]]] = None  # override/augment tsconfig paths


def _load_tsconfig_paths(tsconfig_file: Path) -> Dict[str, List[str]]:
    if not tsconfig_file.exists():
        return {}
    try:
        data = _json_mod.loads(tsconfig_file.read_text(encoding="utf-8", errors="ignore"))
        compiler = (data or {}).get("compilerOptions", {})
        paths = compiler.get("paths", {}) or {}
        base_url = compiler.get("baseUrl", "") or ""
        base_root = (tsconfig_file.parent / base_url).resolve() if base_url else tsconfig_file.parent.resolve()
        normalized: Dict[str, List[str]] = {}
        for alias, arr in paths.items():
            patts = arr if isinstance(arr, list) else [arr]
            norm = []
            for patt in patts:
                patt = patt.replace("*", "")
                p = (base_root / patt).resolve()
                norm.append(p.as_posix())
            normalized[alias] = norm
        return normalized
    except Exception:
        return {}


def _resolve_alias_path(spec: str, alias_map: Dict[str, List[str]]) -> List[str]:
    targets: List[str] = []
    for alias, roots in alias_map.items():
        if spec.startswith(alias):
            suffix = spec[len(alias):]
        else:
            continue
        for root in roots:
            guess = Path(root) / suffix
            candidates = [
                guess,
                guess.with_suffix(".ts"),
                guess.with_suffix(".tsx"),
                guess.with_suffix(".js"),
                guess.with_suffix(".jsx"),
                guess / "index.ts",
                guess / "index.tsx",
                guess / "index.js",
                guess / "index.jsx",
            ]
            for c in candidates:
                if c.exists():
                    targets.append(c.resolve().as_posix())
    # de-dupe keep order
    return list(dict.fromkeys(targets))


@router.post("/resolve_deps", name="resolve_deps")
def resolve_deps(req: ResolveDepsReq = Body(...)) -> dict:
    """
    Parse per-file review .mds (routing JSON, extracted via reviewer.parse_review_md),
    map "dependencies" to repo paths via tsconfig.paths and/or explicit alias overrides.
    Writes reports/deps/resolved_deps.json (stable name for CI diffs).
    """
    try:
        from app.ai.reviewer import parse_review_md  # type: ignore
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"missing reviewer.parse_review_md: {e!r}")

    alias_map: Dict[str, List[str]] = {}
    tsconfig_used = None
    if req.tsconfig_path:
        tsconfig_used = Path(req.tsconfig_path).resolve().as_posix()
        alias_map.update(_load_tsconfig_paths(Path(req.tsconfig_path)))
    else:
        root_ts = Path("tsconfig.json")
        if root_ts.exists():
            tsconfig_used = root_ts.resolve().as_posix()
            alias_map.update(_load_tsconfig_paths(root_ts))

    if req.aliases:
        for k, v in (req.aliases or {}).items():
            arr = v if isinstance(v, list) else [v]
            alias_map.setdefault(k, [])
            alias_map[k].extend(arr)

    resolved: DefaultDict[str, List[str]] = defaultdict(list)
    unresolved: DefaultDict[str, List[str]] = defaultdict(list)

    for md in req.md_paths:
        try:
            txt = Path(md).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            unresolved[md].append("(md_read_error)")
            continue
        parsed = parse_review_md(txt)
        deps = parsed.get("dependencies") or []
        for dep in deps:
            dep = str(dep).strip()
            p = Path(dep)
            if p.exists():
                resolved[md].append(p.resolve().as_posix())
                continue
            if dep.startswith("@"):
                hits = _resolve_alias_path(dep, alias_map)
                if hits:
                    resolved[md].extend(hits)
                else:
                    unresolved[md].append(dep)
            else:
                guess = Path(dep)
                if guess.exists():
                    resolved[md].append(guess.resolve().as_posix())
                else:
                    unresolved[md].append(dep)

    out_resolved = {k: sorted(set(v)) for k, v in resolved.items()}
    out_unresolved = {k: sorted(set(v)) for k, v in unresolved.items() if v}

    out_dir = REPORTS_DIR / "deps"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / "resolved_deps.json"
    out_json.write_text(
        _json_mod.dumps({"resolved": out_resolved, "unresolved": out_unresolved}, indent=2),
        encoding="utf-8",
    )

    return {
        "ok": True,
        "out": out_json.as_posix(),
        "resolved": out_resolved,
        "orphans": sorted({d for arr in out_unresolved.values() for d in arr}),
        "tsconfig_used": tsconfig_used,
    }

