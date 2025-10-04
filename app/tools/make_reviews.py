from __future__ import annotations
import argparse, json, re, time
from pathlib import Path
from typing import Dict, List, Tuple

# Simple keyword→destination mapping (tune as you like)
KEYWORDS: List[Tuple[str, str]] = [
    (r"\bbuyer\b|\bcheckout\b|\bbid\b",             "buyer"),
    (r"\bseller\b|\blisting\b|\binventory\b",       "seller"),
    (r"\blender\b|\bloan\b|\bapr\b|\bcredit\b",     "lender"),
    (r"\bescrow\b|\bclosing\b|\btrust\b",           "escrow"),
    (r"\bdispute\b|\barbitration\b|\bjudge\b",      "disputes"),
    (r"\binspection\b|\bmechanic\b|\bservice\b",    "mechanic"),
    (r"\binsurance\b|\bpolicy\b|\bclaim\b",         "insurance"),
    (r"\bmarketplace\b|\bsearch\b|\bresults?\b",    "marketplace"),
    (r"\bchat\b|\bmessage\b|\bthread\b",            "chat"),
    (r"\buser\b|\bauth\b|\blogin\b|\bsign[- ]?up\b","auth"),
    (r"\badmin\b|\bconfig\b|\bsettings?\b",         "admin"),
    (r"\bfinance\b|\bpayment\b|\binvoice\b",        "finance"),
]

# files we’ll consider for review
EXTS = {".ts", ".tsx", ".js", ".jsx"}

def guess_dest(path: Path, text: str) -> Tuple[str, float, str]:
    """Heuristic: pick a destination folder and confidence with a short reason."""
    hay = f"{path.name.lower()} {text.lower()}"
    best: Tuple[str, float, str] = ("common", 0.30, "Default to common (no strong signals).")
    for pattern, dest in KEYWORDS:
        if re.search(pattern, hay):
            # naive scoring: more patterns that match → higher confidence
            score = 0.7 if dest != "common" else 0.5
            reason = f'Matched keyword rule "{pattern}" → "{dest}"'
            if score > best[1]:
                best = (dest, score, reason)
    # if file already lives under a known domain, bump confidence
    parts = [p.lower() for p in path.parts]
    for _, dest in KEYWORDS:
        if dest in parts:
            bump = min(0.2, 1.0 - best[1])
            best = (dest, best[1] + bump, best[2] + " (directory hint)")
            break
    return best

def scan(root: Path, limit: int) -> List[Dict]:
    files = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in EXTS]
    files.sort(key=lambda p: (p.suffix, p.name.lower()))
    if limit and limit > 0:
        files = files[:limit]

    items: List[Dict] = []
    for p in files:
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            txt = ""
        dest_folder, conf, reason = guess_dest(p, txt)
        # mirror docs under C:\CFH\docs\frontend\... (same subpath starting at \src\… if present)
        subpath = None
        try:
            idx = [i for i, part in enumerate(p.parts) if part.lower() == "src"]
            if idx:
                start = idx[0]
                subpath = Path(*p.parts[start:])  # src\...\File.tsx
        except Exception:
            pass

        items.append({
            "src": str(p),
            "suggested_moves": [
                {
                    "dest": str(p.parent.parent / dest_folder / p.name)  # move across sibling under components/<dest>/
                          if ("components" in [x.lower() for x in p.parts]) else str(p),
                    "confidence": round(float(conf), 3),
                    "reason": reason,
                }
            ],
            "doc_mirror": str(Path(r"C:\CFH\docs\frontend") / (subpath.as_posix() if subpath else p.name).replace("/", "\\"))[:-len(p.suffix)] + ".md",
        })
    return items

def main() -> None:
    ap = argparse.ArgumentParser(description="Generate a reviews JSON artifact from a source tree.")
    ap.add_argument("--root", required=True, help=r"e.g. C:\CFH\frontend\src\components\needsHome")
    ap.add_argument("--limit", type=int, default=25, help="Max files to include")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Root not found or not a directory: {root}")

    items = scan(root, args.limit)
    payload = {
        "root": str(root),
        "generated_at": int(time.time()),
        "count": len(items),
        "items": items,
    }
    reports = Path("reports"); reports.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    out = reports / f"reviews_{stamp}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(str(out))

if __name__ == "__main__":
    main()
