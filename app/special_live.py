from __future__ import annotations
import os
import re
import json
import csv
import uuid
import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone

# .env autoload (safe if missing)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# optional OpenAI client (only used if live and key present)
def _openai_client():
    try:
        from openai import OpenAI  # openai>=1.35,<2
        return OpenAI()
    except Exception as e:
        raise RuntimeError(f"OpenAI client unavailable: {e}")

log = logging.getLogger("special_live")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS = PROJECT_ROOT / "reports"
ART = PROJECT_ROOT / "artifacts" / "generations_special"
ART.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

DEFAULT_SKIP = {
    ".git",".hg",".svn",".yarn",".pnpm-store",".turbo",".next",".cache",
    "node_modules","build","dist","coverage","storybook-static","out","public"
}

def _split_csv(v: str|None) -> list[str]:
    return [p.strip() for p in (v or "").replace(";",",").split(",") if p.strip()]

def _should_skip(path: Path, extra_skips: set[str]) -> bool:
    parts = {p.lower() for p in path.parts}
    return bool(parts & extra_skips)

def scan_roots(roots: list[str], exts: list[str], skip_dirs: list[str]) -> list[dict]:
    exts = [e.lower().lstrip(".") for e in exts]
    skip_set = {s.strip().lower() for s in skip_dirs if s.strip()} | {s.lower() for s in DEFAULT_SKIP}
    inv: list[dict] = []
    for root in roots:
        root = root.strip()
        if not root:
            continue
        rp = Path(root)
        if not rp.exists():
            log.warning("root missing: %s", root)
            continue
        for p in rp.rglob("*"):
            if not p.is_file():
                continue
            if _should_skip(p, skip_set):
                continue
            ext = p.suffix.lower().lstrip(".")
            if ext not in exts:
                continue
            category = "test" if (".test." in p.name or p.name.endswith(".test") or p.parent.name == "tests") else "letters_only" if re.fullmatch(r"[A-Za-z]+", p.stem or "") else "other"
            inv.append({"path": str(p.as_posix()), "size": p.stat().st_size, "ext": ext, "category": category})
    return inv

def _sanitize_name(path: str) -> str:
    # Turn C:/Backup_Projects/CFH/a/b/c.test.ts -> __Backup_Projects__CFH__a__b__c.test.ts
    base = re.sub(r"[:/\\]+", "__", path.strip("/\\"))
    return base

def write_grouped_reports(items: list[dict], run_id: str) -> None:
    # Group by base filename (no extension)
    def base_of(p: str) -> str:
        name = Path(p).name
        stem = name.split(".")[0]
        return stem
    groups: dict[str, list[str]] = {}
    for it in items:
        b = base_of(it["path"])
        groups.setdefault(b, []).append(it["path"])
    # all groups
    all_txt = REPORTS / f"grouped_files_{run_id}.txt"
    with all_txt.open("w", encoding="utf-8") as f:
        f.write(f"## Grouped by base name (run {run_id})\n")
        for name, paths in sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True):
            f.write(f"### {name}  (count={len(paths)})\n")
            for p in paths:
                f.write(f" - {p}\n")
            f.write("\n")
    # letters-only groups
    letters_txt = REPORTS / f"grouped_files_letters_only_{run_id}.txt"
    with letters_txt.open("w", encoding="utf-8") as f:
        f.write(f"## Grouped by base name — letters only (run {run_id})\n")
        for name, paths in sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True):
            if re.fullmatch(r"[A-Za-z]+", name or "") and not name.startswith("$"):
                f.write(f"### {name}  (count={len(paths)})\n")
                for p in paths:
                    f.write(f" - {p}\n")
                f.write("\n")
    # convenience latest pointers
    (REPORTS / "grouped_files.txt").write_text(all_txt.read_text(encoding="utf-8"), encoding="utf-8")
    (REPORTS / "grouped_files_letters_only.txt").write_text(letters_txt.read_text(encoding="utf-8"), encoding="utf-8")

def write_inventory(inv: list[dict], run_id: str) -> None:
    # JSON
    summary = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(inv),
        "samples": inv[:10]
    }
    jpath = REPORTS / f"special_scan_{run_id}.json"
    (REPORTS / "special_scan_latest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    jpath.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    # CSV
    cpath = REPORTS / f"special_inventory_{run_id}.csv"
    with cpath.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["path","size","ext","category"])
        w.writeheader()
        for row in inv:
            w.writerow(row)

def openai_review_for(path: str, model: str) -> dict:
    client = _openai_client()
    # keep prompt tiny to be fast/cheap
    head = ""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            head = fh.read(2000)
    except Exception:
        pass
    prompt = f"File: {path}\nBriefly assess what this file does and list 3-5 TypeScript risks to check when migrating."
    try:
        res = client.chat.completions.create(
            model=model,
            messages=[{"role":"system","content":"You are a concise senior TS migration reviewer."},
                      {"role":"user","content": prompt + "\n\n--- File Head (truncated) ---\n" + head}],
            temperature=0.2,
            max_tokens=200
        )
        text = (res.choices[0].message.content or "").strip()
        return {"note":"openai-live","model":model,"review":text}
    except Exception as e:
        return {"note":"openai-error","error":str(e)}

def process(items: list[dict], run_id: str, limit: int, providers_csv: str, dry_run: bool, model: str) -> list[dict]:
    providers = [p.strip().lower() for p in _split_csv(providers_csv)]
    out: list[dict] = []
    for it in items[:limit]:
        p = it["path"]
        payload = {"run_id": run_id, "path": p, "tier": "Free", "generation": {}}
        if dry_run or ("openai" not in providers):
            payload["generation"] = {"kind": "special-ai-review", "note": "placeholder"}
        else:
            payload["generation"] = openai_review_for(p, model)
        # write artifact
        name = _sanitize_name(p) + ".gen.json"
        (ART / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        out.append(payload)
    return out

def main():
    ap = argparse.ArgumentParser(description="Special LIVE runner (non-destructive).")
    ap.add_argument("--roots", default=os.getenv("AIO_SCAN_ROOTS","C:\\Backup_Projects;D:\\Archives"))
    ap.add_argument("--exts", default=os.getenv("AIO_SPECIAL_EXTS","js,jsx,ts,tsx,md,test.js,test.jsx,test.ts,test.tsx"))
    ap.add_argument("--skip-dirs", default=os.getenv("AIO_SKIP_DIRS",""))
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--providers", default=os.getenv("AIO_PROVIDERS","openai"))
    ap.add_argument("--dry-run", default=os.getenv("AIO_DRY_RUN","true").lower()=="true")
    ap.add_argument("--model", default=os.getenv("AIO_MODEL","gpt-4o-mini"))
    args = ap.parse_args()

    run_id = uuid.uuid4().hex[:8]
    roots = _split_csv(args.roots)
    exts  = [e.lstrip(".") for e in _split_csv(args.exts)]
    skips = _split_csv(args.skip_dirs)

    log.info("scan:start roots=%s exts=%s", roots, exts)
    inv = scan_roots(roots, exts, skips)
    log.info("scan:done count=%d", len(inv))
    write_inventory(inv, run_id)
    write_grouped_reports(inv, run_id)

    log.info("process:start limit=%d providers=%s dry=%s model=%s", args.limit, args.providers, args.dry_run, args.model)
    out = process(inv, run_id, args.limit, args.providers, args.dry_run, args.model)
    log.info("process:done emitted=%d -> artifacts/generations_special/*.gen.json", len(out))
    print(json.dumps({"ok": True, "run_id": run_id, "processed": len(out)}))

if __name__ == "__main__":
    main()
