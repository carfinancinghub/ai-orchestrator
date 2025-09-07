# app/ops.py
from __future__ import annotations
import os, re, json, csv, hashlib, time, subprocess, pathlib
from dataclasses import dataclass, asdict
from typing import Dict, List, Iterable, Tuple, Optional

FRONTEND_EXTS = {".js", ".jsx", ".ts", ".tsx"}
CRYPTO_RX = re.compile(r"""^(
    \$[A-Za-z0-9]{6,}        # $I2H07PR.test.ts, etc.
  | [A-Fa-f0-9]{8,}$         # 8+ hex chars as a bare basename
)$""", re.X)

def _now_id() -> str:
    return time.strftime("%Y%m%d_%H%M%S")

def _hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]

def _is_cryptic_base(base: str) -> bool:
    return bool(CRYPTO_RX.match(base))

def _safe_rel(path: str, root: str) -> str:
    try:
        return str(pathlib.Path(path).resolve().relative_to(pathlib.Path(root).resolve()))
    except Exception:
        return path

def _iter_files(root: str, exts=FRONTEND_EXTS) -> Iterable[str]:
    if not root or not os.path.isdir(root):
        return []
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            p = os.path.join(dirpath, f)
            if os.path.splitext(p)[1].lower() in exts:
                yield p

def fetch_candidates(
    frontend_root: str = r"C:/Backup_Projects/CFH/frontend",
    repo_root: str = ".",
    grouped_out: str = "reports/grouped_files.txt",
    inventory_csv: Optional[str] = None,
) -> Dict[str, List[str]]:
    """
    Scan both the external frontend root and this repo, group by basename,
    filter cryptic/temp names, and write a grouped preview file.
    """
    sources = []
    for root in filter(None, [frontend_root, repo_root]):
        sources.extend(list(_iter_files(root)))

    groups: Dict[str, List[str]] = {}
    for p in sources:
        base = os.path.splitext(os.path.basename(p))[0]
        if _is_cryptic_base(base):
            continue
        groups.setdefault(base, []).append(p)

    os.makedirs(os.path.dirname(grouped_out), exist_ok=True)
    with open(grouped_out, "w", encoding="utf-8") as fh:
        for base in sorted(groups.keys()):
            rels = [p for p in groups[base]]
            fh.write(f"{base}: " + ", ".join(rels) + "\n")

    if inventory_csv:
        os.makedirs(os.path.dirname(inventory_csv), exist_ok=True)
        with open(inventory_csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["base", "path"])
            for base, paths in sorted(groups.items()):
                for p in paths:
                    w.writerow([base, p])

    return groups

def scan_special(frontend_root: str, out_dir: str = "reports") -> str:
    """
    Compatibility shim for ops_cli.py. Produces a JSON summary.
    """
    run_id = f"special_{_now_id()}_{_hash(frontend_root)}"
    grouped_out = os.path.join(out_dir, "grouped_files.txt")
    inventory_csv = os.path.join(out_dir, f"special_inventory_{run_id}.csv")
    summary_json = os.path.join(out_dir, f"special_scan_{run_id}.json")
    groups = fetch_candidates(frontend_root=frontend_root, repo_root=".", grouped_out=grouped_out, inventory_csv=inventory_csv)
    payload = {
        "run_id": run_id,
        "roots": {"frontend_root": frontend_root, "repo_root": os.getcwd()},
        "groups": {k: sorted(v) for k, v in groups.items()},
        "counts": {"groups": len(groups), "files": sum(len(v) for v in groups.values())},
        "outputs": {"grouped": grouped_out, "inventory_csv": inventory_csv, "summary_json": summary_json},
    }
    os.makedirs(out_dir, exist_ok=True)
    with open(summary_json, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    return run_id

# --- Lightweight function extraction (no external deps required) ----------------

JS_FUNC_RX = re.compile(r"""
(?:
    # named function
    (?:export\s+)?function\s+(?P<n1>[A-Za-z_$][A-Za-z0-9_$]*)\s*\(
  |
    # const foo = (...) => or function (...)
    (?:export\s+)?(?:const|let|var)\s+(?P<n2>[A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:async\s+)?(?:\(|function\b)
)
""", re.X)

def extract_functions_from_text(code: str, lang_hint: str) -> List[str]:
    if lang_hint.lower() in ("js", "ts", "tsx", "jsx"):
        names = []
        for m in JS_FUNC_RX.finditer(code):
            names.append(m.group("n1") or m.group("n2"))
        return sorted(set(names))
    # Default/other: Python heuristic
    out = []
    for line in code.splitlines():
        s = line.lstrip()
        if s.startswith("def ") and "(" in s:
            name = s[4:].split("(")[0].strip()
            if name:
                out.append(name)
    return sorted(set(out))

# --- Multi-AI review skeleton ---------------------------------------------------

def _maybe_import_clients():
    oa = gm = gr = None
    try:
        from app.services.llm.openai_client import ask as oa  # type: ignore
    except Exception:
        pass
    try:
        from app.services.llm.google_client import ask as gm  # type: ignore
    except Exception:
        pass
    try:
        from app.services.llm.grok_client import ask as gr  # type: ignore
    except Exception:
        pass
    return oa, gm, gr

def _score_and_recommend(base: str, paths: List[str]) -> Tuple[int, str]:
    score = 10
    if any(p.endswith((".test.ts", ".spec.ts", ".test.tsx", ".spec.tsx")) for p in paths):
        score += 25
    if any(p.endswith((".js", ".jsx")) for p in paths) and any(p.endswith((".ts", ".tsx")) for p in paths):
        score += 35
    score = max(0, min(100, score))
    reco = "discard" if score < 30 else ("keep" if score < 60 else "merge")
    return score, reco

def process_batch(tier: str, groups: Dict[str, List[str]], out_dir="artifacts/generated", report_dir="reports") -> str:
    """
    For each base group, extract function names, run tiered reviews, and
    optionally emit a generated .ts file. Writes a summary JSON.
    """
    run_id = f"batch_{_now_id()}"
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(report_dir, exist_ok=True)
    oa, gm, gr = _maybe_import_clients()

    results = []
    for base, paths in sorted(groups.items()):
        # Concatenate code for quick context (bounded)
        blobs = []
        for p in paths[:6]:
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as fh:
                    code = fh.read()
            except Exception:
                code = ""
            lang_hint = os.path.splitext(p)[1].lstrip(".")
            fns = extract_functions_from_text(code, lang_hint)
            blobs.append({"path": p, "functions": fns, "sample": code[:4000]})
        score, reco = _score_and_recommend(base, paths)

        # Multi-AI reviewers (best-effort; skip if client missing)
        reviews = {}
        prompt = f"Give concise refactor/type hints for: {base}. Functions: {[f for b in blobs for f in b['functions']]}"
        if tier.lower() in ("free", "premium", "wow++") and oa:
            try:
                reviews["openai"] = oa(prompt)
            except Exception as e:
                reviews["openai"] = f"openai_error: {e}"
        if tier.lower() in ("premium", "wow++") and oa:
            try:
                reviews["chatgpt"] = oa(prompt + " Be specific on TS types.")
            except Exception as e:
                reviews["chatgpt"] = f"chatgpt_error: {e}"
        if tier.lower() == "wow++":
            if gm:
                try:
                    reviews["gemini"] = gm(prompt + " Focus on system-level risks.")
                except Exception as e:
                    reviews["gemini"] = f"gemini_error: {e}"
            if gr:
                try:
                    reviews["grok"] = gr(prompt + " Suggest bold refactors.")
                except Exception as e:
                    reviews["grok"] = f"grok_error: {e}"

        # Optional minimal generation artifact (stub)
        gen_path = os.path.join(out_dir, f"{base}.ts")
        with open(gen_path, "w", encoding="utf-8") as fh:
            fh.write("// Generated stub for {}\n".format(base))
            for b in blobs:
                for fn in b["functions"][:5]:
                    fh.write(f"export function {fn}(...args: any[]): any {{ /* TODO */ }}\n")

        results.append({
            "base": base,
            "paths": paths,
            "worth_score": score,
            "recommendation": reco,
            "reviews": {k: (v[:600] if isinstance(v, str) else str(v)) for k, v in reviews.items()},
            "artifact": gen_path,
        })

    report_path = os.path.join(report_dir, f"review_summary_{run_id}.json")
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump({"run_id": run_id, "results": results}, fh, indent=2)
    return report_path

# --- Gates (tsc, test, lint) ---------------------------------------------------

def run_gates(frontend_root: str, run_id: Optional[str] = None) -> str:
    run_id = run_id or f"gates_{_now_id()}"
    out = os.path.join("reports", f"gates_{run_id}.json")
    os.makedirs("reports", exist_ok=True)

    def _run(cmd: List[str], cwd: str) -> Dict[str, str]:
        try:
            p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=False, timeout=30*60)
            return {
                "cmd": " ".join(cmd),
                "code": p.returncode,
                "stdout_head": (p.stdout or "")[-4000:],
                "stderr_head": (p.stderr or "")[-4000:],
            }
        except Exception as e:
            return {"cmd": " ".join(cmd), "code": -999, "error": str(e)}

    results = {
        "tsc": _run(["npm", "run", "-s", "tsc"], frontend_root),
        "test": _run(["npm", "test", "--", "-w=1", "--silent"], frontend_root),
        "lint": _run(["npm", "run", "-s", "lint"], frontend_root),
    }
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"run_id": run_id, "frontend_root": frontend_root, "results": results}, fh, indent=2)
    return out
