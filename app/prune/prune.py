from __future__ import annotations
from pathlib import Path
from typing import List, Tuple
import csv

def make_pruned_map(md_paths: List[Path], out_csv: Path) -> Path:
    # Stub: mark all keeps; you’ll later integrate Gemini consolidation decisions
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["path","action","reason"])
        for p in md_paths:
            w.writerow([str(p), "keep", "initial pilot keep (stub)"])
    return out_csv
