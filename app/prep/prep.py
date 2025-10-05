from __future__ import annotations
import csv, hashlib, os, re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Dict, Tuple

RE_FRONTEND = Path(os.getenv("FRONTEND_ROOT", r"C:\CFH\frontend"))
BLOAT_DIRS = {".git", "node_modules", "dist", "build", ".mypy_cache", ".next", "logs"}

@dataclass
class FileRec:
    path: str
    size: int
    mtime: float
    sha1: str

def iter_candidate_files(module: str) -> Iterable[Path]:
    # module-aware filter; Auctions pilot
    patts = {
        "auctions": re.compile(r"(auction|bid|lot|reserve|seller|buyer|escrow)", re.I),
    }
    rx = patts.get(module, re.compile(re.escape(module), re.I))
    for p in RE_FRONTEND.rglob("*"):
        if any(seg in BLOAT_DIRS for seg in p.parts): continue
        if p.is_file() and rx.search(str(p).replace("\\","/")):
            yield p

def sha1sum(p: Path) -> str:
    h = hashlib.sha1()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def collect(module: str, min_size: int = 1024) -> List[FileRec]:
    seen: Dict[str, FileRec] = {}
    for p in iter_candidate_files(module):
        st = p.stat()
        if st.st_size < min_size:
            continue
        digest = sha1sum(p)
        if digest in seen:
            continue
        seen[digest] = FileRec(
            path=str(p),
            size=st.st_size,
            mtime=st.st_mtime,
            sha1=digest,
        )
    return list(seen.values())

def chunk(lst: List[FileRec], n: int = 30) -> List[List[FileRec]]:
    return [lst[i:i+n] for i in range(0, len(lst), n)]

def write_batches(module: str, rows: List[FileRec], outdir: Path) -> List[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    files: List[Path] = []
    for idx, group in enumerate(chunk(rows, 30), start=1):
        outp = outdir / f"Batch_{module}_{idx}.csv"
        with outp.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["path","size","mtime","sha1"])
            for r in group:
                w.writerow([r.path, r.size, int(r.mtime), r.sha1])
        files.append(outp)
    return files
