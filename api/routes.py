# api/routes.py
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(tags=["convert"])  # meta routes live in app/server.py

# ------------------------------- constants -----------------------------------

CODE_EXTS = {".ts", ".tsx", ".js", ".jsx"}
IGNORE_NAMES = {"desktop.ini", ".ds_store", "thumbs.db"}
IGNORE_SUFFIXES = (".bak", ".tmp", "~")
IGNORE_DIR_PARTS = {"/__mocks__/", "/tests/", "/node_modules/"}
TEST_NAME_RE = re.compile(r"\.(test|spec)\.[a-z0-9]+$", re.I)

BLOAT_DIRS = {".git", "node_modules", "dist", "build", ".mypy_cache", ".next", "logs"}

# ------------------------------- batch prep ----------------------------------

def _sha1sum(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _iter_candidates(frontend_root: Path, module: str) -> Iterable[Path]:
    patterns = {
        "auctions": r"(auction|bid|lot|reserve|seller|buyer|escrow)",
    }
    rx = re.compile(patterns.get(module, re.escape(module)), re.I)
    for p in frontend_root.rglob("*"):
        if any(seg in BLOAT_DIRS for seg in p.parts):
            continue
        if p.is_file() and rx.search(str(p).replace("\\", "/")):
            yield p

def _collect_batch_rows(frontend_root: Path, module: str, min_size: int = 1024):
    seen = {}
    for p in _iter_candidates(frontend_root, module):
        st = p.stat()
        if st.st_size < min_size:
            continue
        digest = _sha1sum(p)
        if digest in seen:
            continue
        seen[digest] = (str(p), st.st_size, int(st.st_mtime), digest)
    return list(seen.values())

def _write_batches(rows, module: str, out_dir: Path, chunk_size: int = 30):
    out_dir.mkdir(parents=True, exist_ok=True)
    outs: List[Path] = []
    for i in range(0, len(rows), chunk_size):
        group = rows[i : i + chunk_size]
        outp = out_dir / f"Batch_{module}_{(i // chunk_size) + 1}.csv"
        with outp.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["path", "size", "mtime", "sha1"])
            for (path, size, mtime, sha1) in group:
                w.writerow([path, size, mtime, sha1])
        outs.append(outp)
    return outs

# ------------------------------- helpers -------------------------------------

def _is_noise(p: Path) -> bool:
    name_l = p.name.lower()
    if name_l in IGNORE_NAMES:
        return True
    if name_l.endswith(IGNORE_SUFFIXES):
        return True
    if TEST_NAME_RE.search(name_l):
        return True
    ppos = p.as_posix().lower()
    for part in IGNORE_DIR_PARTS:
        if part in ppos:
            return True
    return False

def _rel(p: Path, base: Optional[Path] = None) -> str:
    base = base or Path.cwd()
    try:
        return p.resolve().relative_to(base.resolve()).as_posix()
    except Exception:
        return p.as_posix()

def _git_changed_files(base_ref: str, cwd: Optional[Path] = None) -> List[str]:
    try:
        cwd = cwd or Path.cwd()
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
        )
        files = [ln.strip().replace("\\", "/") for ln in result.stdout.splitlines() if ln.strip()]
        return files
    except Exception:
        return []

def _preview_text(rel: str, max_lines: int = 40) -> List[str]:
    try:
        p = Path(rel)
        if not p.exists():
            p = Path(rel.strip("`").strip())
        txt = p.read_text(encoding="utf-8", errors="ignore").splitlines()[:max_lines]
        return txt
    except Exception:
        return ["(snippet unavailable)"]

def _normalize_batch_artifacts(out_dir: Path, batch: Dict[str, Any]) -> Dict[str, Any]:
    fixed: Dict[str, Any] = {}
    # batch_md
    batch_md = batch.get("batch_md")
    if isinstance(batch_md, str) and batch_md:
        fixed["batch_md"] = (out_dir / Path(batch_md).name).as_posix()
    else:
        fixed["batch_md"] = None
    # per-file mds
    mds = batch.get("per_file_mds") or []
    fixed_mds: List[str] = []
    for m in mds:
        try:
            fixed_mds.append((out_dir / Path(m).name).as_posix())
        except Exception:
            pass
    fixed["per_file_mds"] = fixed_mds
    # deps passthrough
    deps = batch.get("dependencies")
    fixed["dependencies"] = deps if isinstance(deps, dict) else {}
    return fixed

def _derive_out_dir(out_paths: List[str]) -> str:
    out_dir = ""
    try:
        candidates: List[str] = []
        # from first written file
        if out_paths:
            first_parent = Path(out_paths[0]).parent
            candidates.append(
                str((Path.cwd() / first_parent).resolve())
                if not first_parent.is_absolute()
                else str(first_parent)
            )
        # fallbacks
        for guess in ("src/_ai_out", "_ai_out", "build/_ai_out"):
            p = Path(guess)
            if p.exists():
                candidates.append(str(p.resolve()))

        def _has_generated_files(root: Path) -> bool:
            return any(root.rglob("*.plan.ts")) or any(root.rglob("*.plan.tsx")) or bool(out_paths)

        for c in candidates:
            cp = Path(c)
            if cp.exists() and cp.is_dir() and _has_generated_files(cp):
                out_dir = str(cp)
                break
    except Exception:
        out_dir = ""
    return out_dir

# ------------------------------ request models --------------------------------

class ConvertTreeReq(BaseModel):
    root: str = "src"
    dry_run: bool = True
    batch_cap: int = 25
    label: Optional[str] = None
    review_tier: str = "free"           # free | premium | wow
    generate_mds: bool = False          # force batch .md even in dry_run
    git_diff_base: Optional[str] = None # e.g., "main" or a SHA
    md_first: bool = False              # when true, produce .mds then return early

class BuildTsReq(BaseModel):
    md_paths: List[str]
    pruned_map: Optional[str] = None
    apply_moves: bool = True
    label: Optional[str] = None

class ConvertPrepReq(BaseModel):
    module: Optional[str] = None  # e.g., "auctions"

class PruneReq(BaseModel):
    md_paths: List[str] = []
    strategy: str = "keep_all"                 # future: "gemini"
    out_csv: Optional[str] = None              # default: reports/prune/pruned_module_map.csv
    reason: Optional[str] = "pilot keep-all"

# --------------------------------- routes -------------------------------------

@router.get("/reports/latest", tags=["meta"], name="reports_latest")
def reports_latest(label: Optional[str] = None):
    base = Path(os.getenv("REPORTS_DIR", "reports"))
    if label:
        base = base / label
    if not base.exists():
        raise HTTPException(status_code=404, detail="Not Found")
    latest: Optional[Path] = None
    for p in base.rglob("*.summary.md"):
        if (latest is None) or (p.stat().st_mtime > latest.stat().st_mtime):
            latest = p
    if not latest:
        raise HTTPException(status_code=404, detail="Not Found")
    preview = latest.read_text(encoding="utf-8", errors="ignore").splitlines()[:20]
    return {
        "ok": True,
        "path": latest.as_posix(),
        "modified": datetime.fromtimestamp(latest.stat().st_mtime).isoformat(),
        "preview": "\n".join(preview),
        "label": label or "",
    }

@router.post("/convert/prep", name="convert_prep")
def convert_prep(req: ConvertPrepReq = Body(...)) -> dict:
    mod = (req.module or "auctions").lower()
    frontend = Path(os.getenv("FRONTEND_ROOT", r"C:\CFH\frontend"))
    batch_dir = Path(os.getenv("REPORTS_DIR", "reports")) / "batches"
    rows = _collect_batch_rows(frontend, mod, min_size=1024)
    outs = _write_batches(rows, mod, batch_dir, chunk_size=30)
    return {"ok": True, "module": mod, "count": len(rows), "batches": [str(o) for o in outs]}

@router.post("/convert/tree", name="convert_tree")
def convert_tree(req: ConvertTreeReq = Body(...)) -> dict:
    root = Path(req.root)
    converted: List[str] = []
    skipped: List[str] = []
    reviews: List[Dict[str, Any]] = []

    # 1) Gather & filter
    if root.exists() and root.is_dir():
        all_items = list(root.rglob("*"))
        items: List[Path] = [p for p in all_items if not _is_noise(p)]

        # friendly listing (cap 200)
        for p in items[:200]:
            (converted if p.is_file() else skipped).append(p.as_posix())

        # candidate code files
        code_files = [p for p in items if p.is_file() and p.suffix.lower() in CODE_EXTS]

        # optional git-diff filter
        if req.git_diff_base:
            changed_rel = set(_git_changed_files(req.git_diff_base, cwd=Path.cwd()))
            if not changed_rel:
                try:
                    from app.ai.reviewer import get_changed_files  # type: ignore
                    changed_rel = set(get_changed_files(req.git_diff_base, cwd=Path.cwd()))
                except Exception:
                    changed_rel = set()
            if changed_rel:
                code_files = [p for p in code_files if _rel(p) in changed_rel]

        # optional mini review (ignore if helper not present)
        cap = max(0, int(req.batch_cap))
        try:
            from app.ai.reviewer import review_file  # type: ignore
        except Exception:
            review_file = None  # type: ignore

        for p in code_files[:cap]:
            if not review_file:
                break
            try:
                r = review_file(
                    str(p),
                    repo_root=os.getenv("FRONTEND_ROOT", r"C:\CFH\frontend"),
                )
                reviews.append(
                    {
                        "file": p.as_posix(),
                        "routing": r.get("routing", {}),
                        "markdown": r.get("markdown", ""),
                    }
                )
            except Exception as e:
                reviews.append(
                    {
                        "file": p.as_posix(),
                        "error": repr(e),
                        "routing": {"suggested_moves": []},
                        "markdown": "",
                    }
                )

    # 2) response scaffold
    resp: Dict[str, Any] = {
        "ok": True,
        "root": str(root),
        "dry_run": req.dry_run,
        "converted": converted,
        "skipped": skipped,
        "reviews_count": len(reviews),
        "reviews": reviews,
        "artifacts": {},
        "label": req.label or "",
    }

    # 3) persist JSON
    reports_dir = Path(os.getenv("REPORTS_DIR", "reports"))
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = reports_dir / (req.label or "")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"convert_dryrun_{stamp}.json"
    try:
        out.write_text(json.dumps(resp, ensure_ascii=False, indent=2), encoding="utf-8")
        resp["artifact"] = out.as_posix()
    except Exception as e:
        resp["artifact_error"] = repr(e)

    # 4) summary markdown
    try:
        summary_path = out.with_suffix(".summary.md")
        lines: List[str] = []
        lines.append(f"# Convert Dry-Run Summary — {stamp}\n")
        lines.append(f"- Root: `{resp['root']}`")
        lines.append(f"- Dry run: `{resp['dry_run']}`")
        if req.label:
            lines.append(f"- Label: `{req.label}`")
        if req.git_diff_base:
            lines.append(f"- Git diff base: `{req.git_diff_base}`")
        lines.append(f"- Reviews: `{resp['reviews_count']}`")
        lines.append(f"- Converted listed: `{len(resp['converted'])}`  • Skipped listed: `{len(resp['skipped'])}`\n")

        TOP = min(10, len(reviews))
        if TOP:
            lines.append("## Top Reviewed Files\n")
            for r in reviews[:TOP]:
                file = r.get("file", "")
                moves = r.get("routing", {}).get("suggested_moves", [])
                if moves:
                    dest = moves[0].get("dest", "")
                    conf = moves[0].get("confidence", "")
                    lines.append(f"- `{file}` → `{dest}` (conf: {conf})")
                else:
                    lines.append(f"- `{file}` (no suggestion)")

        if req.git_diff_base:
            try:
                changed_rel = _git_changed_files(req.git_diff_base, cwd=Path.cwd())
                if changed_rel:
                    head = min(25, len(changed_rel))
                    lines.append("\n## Changed Files (git diff)\n")
                    for rel in changed_rel[:head]:
                        lines.append(f"- `{rel}`")
                    if len(changed_rel) > head:
                        lines.append(f"... and {len(changed_rel) - head} more")
            except Exception:
                pass

        summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        resp["summary"] = summary_path.as_posix()
    except Exception as e:
        resp["summary_error"] = repr(e)

    # 5) optional batch .md generation (Gemini-first happens inside reviewer)
    try:
        should_batch = (not req.dry_run) or bool(req.generate_mds) or bool(req.md_first)
        if should_batch:
            try:
                cand_paths = [p.as_posix() for p in code_files]  # type: ignore[name-defined]
            except Exception:
                cand_paths = [p for p in converted if p.endswith((".ts", ".tsx", ".js", ".jsx"))]
            cand_paths = cand_paths[:max(1, int(req.batch_cap))]

            if not cand_paths:
                batch_path = (out_dir / f"batch_review_{stamp}.md")
                batch_path.write_text(
                    "# Batch Review — (no candidates)\n\n"
                    f"_Root:_ `{resp['root']}`  • _Label:_ `{req.label or ''}`\n\n"
                    "No code candidates detected for this batch.\n",
                    encoding="utf-8",
                )
                resp["artifacts"] = {"mds": [], "batch_md": batch_path.as_posix()}
            else:
                batch: Dict[str, Any] = {}
                try:
                    from app.ai.reviewer import review_batch  # type: ignore
                except Exception:
                    review_batch = None  # type: ignore

                if review_batch:
                    try:
                        batch = review_batch(
                            cand_paths,
                            tier=req.review_tier,
                            label=None,          # avoid nested subdir duplication
                            reports_dir=out_dir, # write into resolved out_dir
                        ) or {}
                    except Exception as e:
                        resp.setdefault("errors", []).append({"where": "batch_mds/run", "error": repr(e)})

                fixed = _normalize_batch_artifacts(out_dir, req.label or "", batch)

                batch_md = fixed.get("batch_md")
                if not batch_md:
                    batch_path = (out_dir / f"batch_review_{stamp}.md")
                    lines = [
                        f"# Fallback Heuristic Batch Review — {req.review_tier}",
                        "",
                        f"_Root:_ `{resp['root']}`  • _Label:_ `{req.label or ''}`",
                        "",
                    ]
                    for rel in cand_paths:
                        lines.append(f"### File: `{rel}`")
                        lines.append("")
                        lines.append("```")
                        lines.extend(_preview_text(rel, max_lines=40))
                        lines.append("```")
                        lines.append("")
                    batch_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    batch_md = batch_path.as_posix()

                resp["artifacts"] = {
                    "mds": fixed.get("per_file_mds", []),
                    "batch_md": batch_md,
                    "deps": fixed.get("dependencies", {}),
                }

            if req.md_first:
                resp["next_step"] = "build_ts"
                return resp

    except Exception as e:
        resp.setdefault("errors", []).append({"where": "batch_mds/top", "error": repr(e)})

    return resp

@router.post("/build_ts", name="build_ts")
def build_ts(req: BuildTsReq = Body(...)) -> dict:
    """
    Build TS/TSX files from a list of .plan.md docs.
    - Returns { ok, written, errors, label, out_dir }
    - If you already have a builder in your codebase, we call it.
      Otherwise we fall back to a safe stub that writes .plan.tsx files
      into src/_ai_out so downstream steps keep working.
    """
    written: List[str] = []
    errors: List[str] = []

    # 1) try your existing builder if present
    used_native = False
    try:
        # Example: app.prep.ts_builder.build_ts_from_plans(md_paths, pruned_map, label)
        from app.prep.ts_builder import build_ts_from_plans  # type: ignore
        res = build_ts_from_plans(req.md_paths, req.pruned_map, req.label)
        # Expect either list[str] or dict with "written"
        if isinstance(res, list):
            written = [str(p) for p in res]
        elif isinstance(res, dict):
            written = [str(p) for p in res.get("written", [])]
            errors.extend([str(e) for e in res.get("errors", [])])
        used_native = True
    except Exception as e:
        # no native builder; we’ll fall back below
        if os.getenv("ORCH_VERBOSE", "0") == "1":
            errors.append(f"native_builder_unavailable: {repr(e)}")

    # 2) safe fallback stub (keeps the pipeline usable)
    if not used_native:
        out_root = Path("src") / "_ai_out"
        out_root.mkdir(parents=True, exist_ok=True)
        for md in req.md_paths:
            try:
                mdp = Path(md)
                name = mdp.name.replace(".plan.md", ".plan.tsx")
                outp = out_root / name
                header = (
                    f"/**\n"
                    f" * GENERATED STUB FROM PLAN\n"
                    f" * plan: {mdp.as_posix()}\n"
                    f" * date: {datetime.utcnow().isoformat()}Z\n"
                    f" */\n\n"
                )
                # Minimal TSX that references the plan; real impl can replace this.
                body = (
                    f"{header}"
                    f"export default function PlanStub() {{\n"
                    f"  return <pre>{json.dumps(mdp.as_posix())}</pre>;\n"
                    f"}}\n"
                )
                outp.write_text(body, encoding="utf-8")
                written.append(_rel(outp))
            except Exception as e:
                errors.append(f"{md}: {repr(e)}")

    out_dir = _derive_out_dir(written)

    return {
        "ok": len(errors) == 0,
        "written": written,
        "errors": errors,
        "label": req.label or "",
        "out_dir": out_dir,
    }

@router.post("/prune", tags=["convert"], name="prune")
def prune(req: PruneReq) -> dict:
    """
    Pilot prune:
      - strategy="keep_all": write CSV 'path,action,reason' marking each .md as keep
      - strategy="gemini"   : sample up to 10 .md files, ask Gemini to consolidate and
                              emit CSV rows path,action,reason (keep|list|delete + why)
    """
    reports_dir = Path(os.getenv("REPORTS_DIR", "reports"))
    prune_dir = reports_dir / "prune"
    prune_dir.mkdir(parents=True, exist_ok=True)
    out_csv = Path(req.out_csv) if req.out_csv else (prune_dir / "pruned_module_map.csv")

    # sanitize & de-dupe inputs; only keep files that actually exist
    paths: list[str] = []
    for p in req.md_paths:
        try:
            pp = Path(p)
            if pp.exists() and pp.is_file():
                paths.append(str(pp.resolve()))
        except Exception:
            continue
    paths = sorted(set(paths))

    strat = (req.strategy or "keep_all").lower()

    if strat == "keep_all":
        # write CSV with LF for git friendliness
        with out_csv.open("w", encoding="utf-8", newline="\n") as f:
            f.write("path,action,reason\n")
            for p in paths:
                f.write(f"\"{p}\",keep,\"{req.reason or 'pilot keep-all'}\"\n")
        # repo-relative if possible (nice for logs)
        try:
            csv_rel = str(out_csv.relative_to(Path.cwd())).replace("\\", "/")
        except Exception:
            csv_rel = out_csv.as_posix()
        return {"ok": True, "strategy": "keep_all", "count": len(paths), "csv": csv_rel}

    if strat == "gemini":
        try:
            import google.generativeai as genai  # type: ignore
        except Exception as e:
            return {"ok": False, "strategy": "gemini", "error": f"gemini_sdk_missing: {e!r}"}

        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash-latest")
        if not api_key:
            return {"ok": False, "strategy": "gemini", "error": "missing GOOGLE_API_KEY/GEMINI_API_KEY"}

        # sample up to 10 .md for consolidation (tune as you like)
        sample = paths[:10]

        def _read(p: str) -> str:
            try:
                return Path(p).read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                return f"(read error for {p}: {e!r})"

        prompt_parts = [
            "You are consolidating overlapping review markdown files from a codebase.",
            "For each input file, decide an action: keep | list | delete.",
            "If multiple files are duplicates or trivially overlapping, prefer a single canonical file and mark the others delete or list.",
            "When you say 'list', it means keep temporarily, but mark reason why it isn't canonical.",
            "Also unify shared types (e.g., BidProps) in your reasoning, but DO NOT output types—only the CSV rows.",
            "",
            "Output STRICT CSV body rows **without header**, columns: path,action,reason",
            "Rules:",
            "- No code fences.",
            "- No commentary beyond the CSV rows.",
            "- One file per line.",
            "",
        ]
        for p in sample:
            prompt_parts += [f"--- FILE: {p}", _read(p)]
        prompt = "\n".join(prompt_parts)

        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            resp = model.generate_content(
                prompt,
                generation_config={"max_output_tokens": 1500},
                safety_settings=None,
                request_options={"timeout": float(os.getenv("REVIEW_TIMEOUT_S", "30"))},
            )
            text = (getattr(resp, "text", "") or "").strip()
        except Exception as e:
            return {"ok": False, "strategy": "gemini", "error": f"gemini_call_error: {e!r}"}

        # write header + LLM rows
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        with out_csv.open("w", encoding="utf-8", newline="\n") as f:
            f.write("path,action,reason\n")
            for line in text.splitlines():
                line = line.strip()
                if not line or line.lower().startswith("path,"):
                    continue
                f.write(line + "\n")

        try:
            csv_rel = str(out_csv.relative_to(Path.cwd())).replace("\\", "/")
        except Exception:
            csv_rel = out_csv.as_posix()

        return {"ok": True, "strategy": "gemini", "count": len(sample), "csv": csv_rel}

    # unknown strategy
    return {"ok": False, "strategy": strat, "error": "unknown strategy"}
@router.post("/resolve_deps", tags=["convert"], name="resolve_deps")
def resolve_deps(req: ResolveDepsReq) -> dict:
    """
    Parse per-file review .mds (routing JSON), map "dependencies" to real repo paths
    via tsconfig.paths and/or explicit alias overrides. Writes an artifact in reports/.
    """
    try:
        from app.ai.reviewer import parse_review_md  # type: ignore
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"missing reviewer.parse_review_md: {e!r}")

    alias_map: dict[str, list[str]] = {}
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

    resolved: DefaultDict[str, list[str]] = defaultdict(list)
    unresolved: DefaultDict[str, list[str]] = defaultdict(list)

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

    reports_dir = Path(os.getenv("REPORTS_DIR", "reports")) / "deps"
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = reports_dir / "resolved_deps.json"  # stable name for CI diffs
    out_json.write_text(_json_mod.dumps({"resolved": out_resolved, "unresolved": out_unresolved}, indent=2), encoding="utf-8")

    return {
        "ok": True,
        "out": out_json.as_posix(),
        "resolved": out_resolved,
        "orphans": sorted({d for arr in out_unresolved.values() for d in arr}),
    }
# === END: /resolve_deps =======================================================
