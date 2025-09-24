**********************
PowerShell transcript start
Start time: 20250912103228
Username: Agasi\Agasi5
RunAs User: Agasi\Agasi5
Configuration Name: 
Machine: AGASI (Microsoft Windows NT 10.0.26100.0)
Host Application: C:\Program Files\PowerShell\7\pwsh.dll
Process ID: 63212
PSVersion: 7.5.3
PSEdition: Core
GitCommitId: 7.5.3
OS: Microsoft Windows 10.0.26100
Platform: Win32NT
PSCompatibleVersions: 1.0, 2.0, 3.0, 4.0, 5.0, 5.1, 6.0, 7.0
PSRemotingProtocolVersion: 2.3
SerializationVersion: 1.1.0.1
WSManStackVersion: 3.0
**********************
PS C:\c\ai-orchestrator>
PS C:\c\ai-orchestrator>
(.venv) $new = @'
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
'@
PS C:\c\ai-orchestrator>
(.venv) $new | Set-Content app\review_multi.py -Encoding UTF8
PS C:\c\ai-orchestrator>
PS C:\c\ai-orchestrator>
(.venv) # B) Tiny CLI to exercise it
PS C:\c\ai-orchestrator>
(.venv) @'
# app/review_cli.py
import argparse, sys
from app.review_multi import run_multi_ai_review

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", nargs="+", required=True)
    ap.add_argument("--out", default="artifacts/reviews")
    args = ap.parse_args()
    run_id = run_multi_ai_review(args.files, out_root=args.out)
    print({"ok": True, "run_id": run_id})

if __name__ == "__main__":
    main()
'@ | Set-Content app\review_cli.py -Encoding UTF8
PS C:\c\ai-orchestrator>
PS C:\c\ai-orchestrator>
(.venv) # C) Smoke run on a few files we know exist
PS C:\c\ai-orchestrator>
(.venv) python -m app.review_cli --files app\ops.py app\ops_cli.py 2>&1 | Tee-Object -FilePath $log -Append
>> TerminatingError(out-file): "The process cannot access the file 'C:\c\ai-orchestrator\reports\debug\multi_ai_adapter_20250912_1032.md' because it is being used by another process."
>> TerminatingError(out-file): "The process cannot access the file 'C:\c\ai-orchestrator\reports\debug\multi_ai_adapter_20250912_1032.md' because it is being used by another process."
The process cannot access the file 'C:\c\ai-orchestrator\reports\debug\multi_ai_adapter_20250912_1032.md' because it is being used by another process.
out-file: The process cannot access the file 'C:\c\ai-orchestrator\reports\debug\multi_ai_adapter_20250912_1032.md' because it is being used by another process.
PS C:\c\ai-orchestrator>
PS C:\c\ai-orchestrator>
(.venv) # D) Commit + push + print URL
