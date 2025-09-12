# app/review_multi.py
from __future__ import annotations
import json, os, uuid
from pathlib import Path
from typing import Dict, Any, List

TIERS = ["Free","Premium","WowPlusPlus"]

def _ensure(p: Path): p.mkdir(parents=True, exist_ok=True)

def _score(payload: Dict[str, Any]) -> int:
    # Very dumb worth_score placeholder. Replace with your heuristics.
    size = payload.get("src_bytes", 0)
    return max(0, min(100, 10 + (size // 1000)))

def run_multi_ai_review(file_paths: List[str], out_root: str="artifacts/reviews") -> str:
    run_id = uuid.uuid4().hex[:8]
    out = Path(out_root) / run_id
    for t in TIERS:
        _ensure(out / t)

    for fp in file_paths:
        p = Path(fp)
        meta = {
            "file": str(p),
            "src_bytes": p.stat().st_size if p.exists() else 0,
            "model_free": os.getenv("AIO_MODEL","gpt-4o-mini"),
            "providers": os.getenv("AIO_PROVIDERS","openai").split(","),
        }
        review = {
            "rubric": {
                "type_coverage": 0,
                "refactor_quality": 0,
                "test_coverage": 0,
                "future_readiness": 0
            },
            "worth_score": _score(meta),
            "decision": "keep"  # or "merge"/"discard" later
        }
        for tier in TIERS:
            data = {"tier": tier, "meta": meta, "review": review}
            out_file = out / tier / (p.name + ".json")
            out_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[multi-ai] wrote tiered reviews for {len(file_paths)} files into {out}")
    return run_id
