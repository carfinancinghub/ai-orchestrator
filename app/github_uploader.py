"""COD1 scaffold: uploader planning (non-destructive).
When AIO_UPLOAD_TS=1, generate a plan file listing files that would be pushed.
"""
import os, glob, json

def upload_generated_to_github(run_id: str, branch_prefix: str="ts-migration/generated") -> str:
    if os.getenv("AIO_UPLOAD_TS","0") != "1":
        return ""
    paths = sorted(glob.glob("artifacts/generated/**/*", recursive=True))
    plan = {
        "run_id": run_id,
        "branch": f"{branch_prefix}-{run_id}",
        "count": len(paths),
        "files": paths,
        "note": "scaffold only; switch to gh CLI or API for actual push"
    }
    out = os.path.join("reports","debug", f"upload_plan_{run_id}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out,"w",encoding="utf-8") as fh:
        json.dump(plan, fh, indent=2)
    return out