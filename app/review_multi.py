from __future__ import annotations
import hashlib, json, os, time
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass
class ReviewTierResult:
    tier: str
    provider: str
    rubric: dict
    worth_score: int
    decision: str  # keep | merge | discard

def _score_to_decision(score: int) -> str:
    if score >= 80: return "keep"
    if score >= 50: return "merge"
    return "discard"

def _fake_rubric(seed: str) -> dict:
    h = int(hashlib.sha256(seed.encode()).hexdigest(), 16) % 50
    return {
        "type_coverage": 60 + (h % 40),
        "refactor_quality": 55 + (h % 45),
        "test_coverage": 50 + (h % 50),
        "future_readiness": 50 + (h % 50),
    }

def _review_for_file(run_id: str, file_rel: str) -> list[ReviewTierResult]:
    r1 = ReviewTierResult("Free", "openai", _fake_rubric(file_rel+"free"), 0, "")
    r2 = ReviewTierResult("Premium", "openai", _fake_rubric(file_rel+"prem"), 0, "")
    r3 = ReviewTierResult("Wow++", "gemini", _fake_rubric(file_rel+"wowg"), 0, "")
    r4 = ReviewTierResult("Wow++", "grok", _fake_rubric(file_rel+"wowx"), 0, "")
    results = [r1, r2, r3, r4]
    for r in results:
        r.worth_score = max(0, min(100, int(0.25*sum(r.rubric.values()))))
        r.decision = _score_to_decision(r.worth_score)
    return results

def persist_review_summary(out_dir: Path, run_id: str, file_rel: str, results: list[ReviewTierResult]):
    out_dir.mkdir(parents=True, exist_ok=True)
    data = [asdict(r) for r in results]
    with (out_dir / f"review_multi_{run_id}.json").open("w", encoding="utf-8") as f:
        json.dump({"file": file_rel, "results": data, "ts": int(time.time())}, f, ensure_ascii=False, indent=2)

def scan_and_review():
    run_id = os.environ.get("AIO_RUN_ID", str(int(time.time())))
    out_root = Path(os.environ.get("AIO_OUTPUT_DIR", "artifacts"))
    gen_dirs = [out_root / "generated", out_root / "staging" / "local" / "main"]
    reviews_dir = out_root / "reviews" / run_id

    count = 0
    for base in gen_dirs:
        if not base.exists(): 
            continue
        for p in base.rglob("*"):
            if p.suffix.lower() in (".ts", ".tsx"):
                file_rel = p.as_posix()
                results = _review_for_file(run_id, file_rel)
                persist_review_summary(reviews_dir, run_id, file_rel, results)
                count += 1
    print(f"[reviews] wrote reviews for {count} files into {reviews_dir}")

if __name__ == "__main__":
    scan_and_review()
