from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime
import json

router = APIRouter()

@router.get("/version")
def version():
    return {"service": "ai-orchestrator", "version": "0.1.0"}

class PromptRequest(BaseModel):
    prompt_key: str
    tier: str = "free"  # free | premium | wow++
    root: str
    js:  list[str] | None = None
    jsx: list[str] | None = None
    ts:  list[str] | None = None
    tsx: list[str] | None = None
    threshold: int = 1200

@router.post("/run-one")
def run_one(req: PromptRequest):
    root = Path(req.root)
    if not root.exists():
        raise HTTPException(status_code=400, detail=f"Root not found: {root}")

    def count_globs(globs):
        if not globs:
            return 0, []
        total = 0
        examples: list[str] = []
        for pattern in globs:
            # Path.rglob handles ** patterns even when pattern includes folders like 'src/**/*.ts'
            for p in root.rglob(pattern):
                if p.is_file():
                    total += 1
                    if len(examples) < 50:
                        examples.append(str(p))
        return total, examples

    counts = {}
    samples = {}

    counts["js"],  samples["js"]  = count_globs(req.js  or ["src/**/*.js"])
    counts["jsx"], samples["jsx"] = count_globs(req.jsx or ["src/**/*.jsx"])
    counts["ts"],  samples["ts"]  = count_globs(req.ts  or ["src/**/*.ts"])
    counts["tsx"], samples["tsx"] = count_globs(req.tsx or ["src/**/*.tsx"])

    in_root = sum(counts.values())
    stop = in_root <= req.threshold

    artifacts = Path("artifacts")
    artifacts.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    log_path = artifacts / f"one_prompt_{ts}.log"

    with log_path.open("w", encoding="utf-8") as f:
        f.write(f"Run-ID: run-{ts}Z\n")
        f.write(f"Prompt: {req.prompt_key}\nTier: {req.tier}\nRoot: {root}\n")
        f.write(f"Counts: {json.dumps(counts)}\n")
        f.write("Sample (first 50 per kind):\n")
        for kind in ("js","jsx","ts","tsx"):
            for s in samples[kind]:
                f.write(f"  {kind}: {s}\n")
        f.write(f"Decision: {'stop' if stop else 'continue'} (in_root={in_root} threshold={req.threshold})\n")

    return {
        "ok": True,
        "counts": counts,
        "in_root": in_root,
        "threshold": req.threshold,
        "stop": stop,
        "log_path": str(log_path.resolve()),
    }
