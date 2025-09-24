# app/health_server.py
import os
from pathlib import Path
from fastapi import FastAPI
from pydantic import BaseModel
import hashlib
import json

APP_ROOT = Path(__file__).resolve().parents[1]  # C:\c\ai-orchestrator
REPORTS = APP_ROOT / "reports"
ART_GEN = APP_ROOT / "artifacts" / "generated"
REVIEWS = APP_ROOT / "artifacts" / "reviews"

app = FastAPI(title="ai-orchestrator health")

class Health(BaseModel):
    status: str
    version: str
    env: dict
    latest_run_id: str | None
    generated_count: int
    reviews_count: int
    consolidation_csv: str | None
    consolidation_uniques: int | None

def _latest_run_id() -> str | None:
    p = REPORTS / "latest_run_id.txt"
    if p.exists():
        try:
            return p.read_text(encoding="utf-8").strip()
        except Exception:
            return None
    return None

def _count_generated() -> int:
    if not ART_GEN.exists():
        return 0
    return sum(1 for _ in ART_GEN.rglob("*") if _.is_file() and _.suffix.lower() in (".ts", ".tsx"))

def _count_reviews(run_id: str | None) -> int:
    if not run_id:
        return 0
    folder = REVIEWS / run_id
    if not folder.exists():
        return 0
    return sum(1 for _ in folder.rglob("*.json") if _.is_file() and _.stat().st_size > 3)

def _consolidation_csv_info():
    # find a recent consolidation csv like consolidation_YYYYMMDD.csv
    if not REPORTS.exists():
        return None, None
    candidates = sorted(REPORTS.glob("consolidation_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return None, None
    csv_path = candidates[0]
    try:
        import csv as _csv
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = _csv.DictReader(f)
            sha1s = set()
            for row in reader:
                s = (row.get("sha1") or "").strip()
                if s:
                    sha1s.add(s)
        return str(csv_path), len(sha1s)
    except Exception:
        return str(csv_path), None

@app.get("/health", response_model=Health)
def health():
    run_id = _latest_run_id()
    gen_count = _count_generated()
    rev_count = _count_reviews(run_id)
    csv_path, uniques = _consolidation_csv_info()
    return Health(
        status="ok",
        version=os.environ.get("AIO_VERSION", "v0.3.8"),
        env={
            "AIO_SKIP_GH": os.environ.get("AIO_SKIP_GH", ""),
            "AIO_REPO": os.environ.get("AIO_REPO", "carfinancinghub/ai-orchestrator"),
        },
        latest_run_id=run_id,
        generated_count=gen_count,
        reviews_count=rev_count,
        consolidation_csv=csv_path,
        consolidation_uniques=uniques,
    )
