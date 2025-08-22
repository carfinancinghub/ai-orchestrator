"""
Path: core/js_auditor.py
Parse Markdown inventories of JS/TS files, de-dup, prefer TS/TSX,
produce a conversion plan for remaining JS/JSX, with optional filters.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple, Optional
import re
from datetime import datetime

ROW_RE = re.compile(r"^\|\s*(?P<path>[^|]+?)\s*\|\s*(?P<size>\d+)\s*\|\s*(?P<mtime>[^|]+?)\s*\|\s*$")
TEST_PAT = re.compile(r"(^|[/\\])(tests?|__tests__)([/\\]|$)|[.](test|spec)[.]", re.I)

@dataclass
class Entry:
    path: str
    size: int
    mtime: float
    stem: str
    ext: str
    dir: str

class JSAuditor:
    exts = {".js", ".jsx", ".ts", ".tsx"}

    def parse_md_files(self, md_paths: List[str]) -> List[Entry]:
        out: List[Entry] = []
        for mp in md_paths:
            p = Path(mp)
            if not p.exists():
                continue
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                m = ROW_RE.match(line)
                if not m:
                    continue
                fpath = m.group("path").strip().replace("\\", "/")
                ext = Path(fpath).suffix.lower()
                if ext not in self.exts:
                    continue
                size = int(m.group("size"))
                try:
                    mt = datetime.fromisoformat(m.group("mtime").strip()).timestamp()
                except Exception:
                    mt = 0.0
                path_obj = Path(fpath)
                out.append(Entry(
                    path=fpath,
                    size=size,
                    mtime=mt,
                    stem=path_obj.stem,
                    ext=ext,
                    dir=str(path_obj.parent).replace("\\", "/"),
                ))
        return out

    def plan(
        self,
        entries: List[Entry],
        *,
        size_min_bytes: int = 0,
        exclude_regex: Optional[str] = None,
        same_dir_only: bool = False,
    ) -> Dict[str, List[str] | Dict[str, int] | str]:
        # pre-filter: size and exclude
        if size_min_bytes > 0:
            entries = [e for e in entries if e.size >= size_min_bytes]
        if exclude_regex:
            ex = re.compile(exclude_regex, re.I)
            entries = [e for e in entries if not ex.search(e.path)]

        # dedup: keep newest per (stem, ext, size, dir) so same-name in different dirs are separate when needed
        latest: Dict[Tuple[str, str, int, str], Entry] = {}
        for e in entries:
            k = (e.stem, e.ext, e.size, e.dir)
            if k not in latest or e.mtime > latest[k].mtime:
                latest[k] = e
        dedup = list(latest.values())

        # group
        if same_dir_only:
            # group by (dir, stem)
            keyfn = lambda e: (e.dir, e.stem)
        else:
            # group by stem (across dirs)
            keyfn = lambda e: e.stem

        by_key: Dict[Tuple[str, ...] | str, List[Entry]] = {}
        for e in dedup:
            by_key.setdefault(keyfn(e), []).append(e)

        keep_ts_tsx: List[str] = []
        drop_js_already_converted: List[str] = []
        convert_candidates: List[str] = []
        tests_skipped: List[str] = []

        for _, lst in by_key.items():
            ts_like = [e for e in lst if e.ext in {".ts", ".tsx"}]
            js_like = [e for e in lst if e.ext in {".js", ".jsx"}]
            if same_dir_only:
                ts_dirs = {e.dir for e in ts_like}
                # keep TS in the group (all)
                keep_ts_tsx.extend(sorted(e.path for e in ts_like))
                for j in js_like:
                    if j.dir in ts_dirs:
                        drop_js_already_converted.append(j.path)
                    else:
                        if TEST_PAT.search(j.path):
                            tests_skipped.append(j.path)
                        else:
                            convert_candidates.append(j.path)
            else:
                if ts_like:
                    keep_ts_tsx.extend(sorted(e.path for e in ts_like))
                    for j in js_like:
                        drop_js_already_converted.append(j.path)
                else:
                    for j in js_like:
                        if TEST_PAT.search(j.path):
                            tests_skipped.append(j.path)
                        else:
                            convert_candidates.append(j.path)

        keep_ts_tsx.sort(); drop_js_already_converted.sort(); convert_candidates.sort(); tests_skipped.sort()
        counts = {
            "dedup": len(dedup),
            "keep_ts_tsx": len(keep_ts_tsx),
            "drop_js_already_converted": len(drop_js_already_converted),
            "convert_candidates": len(convert_candidates),
            "tests_skipped": len(tests_skipped),
        }
        return {
            "counts": counts,
            "keep_ts_tsx": keep_ts_tsx,
            "drop_js_already_converted": drop_js_already_converted,
            "convert_candidates": convert_candidates,
            "tests_skipped": tests_skipped,
            "workspace_root": str(Path.cwd()),
        }
