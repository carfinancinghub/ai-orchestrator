import json
from pathlib import Path
from app.ai.reviewer import review_batch

label = "auctions_wow"
paths = [p.strip() for p in Path(f"reports/paths_{label}.txt").read_text(encoding="utf-8").splitlines() if p.strip()]

res = review_batch(paths, tier="wow", label=label, md_first=True)
print(json.dumps(res, indent=2))
