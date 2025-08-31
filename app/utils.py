# Path: C:\c\ai-orchestrator\app\utils.py
# Version: 0.1.0
# Last Updated: 2025-08-30 22:40 PDT
# Purpose: Utility functions for CFH AI-Orchestrator
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def emit_migration_list(run_id: str, ts_tsx_candidates: list) -> None:
    ARTIFACTS_ROOT = Path("artifacts")
    migration_path = ARTIFACTS_ROOT / f"migration_list_{run_id}.csv"
    migration_path.parent.mkdir(parents=True, exist_ok=True)
    with migration_path.open("w", encoding="utf-8") as f:
        f.write("repo,branch,path\n")
        for c in ts_tsx_candidates:
            f.write(f"{c.repo},{c.branch},{c.src_path}\n")
    logger.info(f"Migration list written to {migration_path}")