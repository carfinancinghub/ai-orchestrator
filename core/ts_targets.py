"""
Path: core/ts_targets.py
Discover JS/TS conversion candidates and compute target paths.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

JS_EXTS = {".js", ".jsx"}
TS_EXTS = {".ts", ".tsx"}
TEST_SUFFIXES = {".test.js", ".test.jsx", ".test.ts", ".test.tsx"}


@dataclass
class ConversionTarget:
    src: Path
    ts_target: Path
    test_target: Optional[Path]
    kind: str  # "component"|"module"|"test"


def _is_test_file(p: Path) -> bool:
    name = p.name.lower()
    for suf in TEST_SUFFIXES:
        if name.endswith(suf):
            return True
    return name.endswith(".spec.js") or name.endswith(".spec.jsx")


def suggest_ts_filename(src: Path) -> Path:
    if src.suffix.lower() == ".jsx":
        return src.with_suffix(".tsx")
    if src.suffix.lower() == ".js":
        # heuristic: if file likely contains JSX, caller may adjust to .tsx later
        return src.with_suffix(".ts")
    return src


def suggest_test_filename(src: Path) -> Optional[Path]:
    name = src.name
    if name.endswith((".test.js", ".test.jsx")):
        return src.with_name(name.rsplit(".test.", 1)[0] + ".test.ts") if name.endswith(".test.js") else src.with_name(name.rsplit(".test.", 1)[0] + ".test.tsx")
    if name.endswith((".spec.js", ".spec.jsx")):
        return src.with_name(name.rsplit(".spec.", 1)[0] + ".spec.ts") if name.endswith(".spec.js") else src.with_name(name.rsplit(".spec.", 1)[0] + ".spec.tsx")
    return None


def find_conversion_candidates(root: Path, includes: Optional[Iterable[str]] = None, excludes: Optional[Iterable[str]] = None) -> List[ConversionTarget]:
    root = root.resolve()
    allow: Optional[set[str]] = set(includes) if includes else None
    deny: set[str] = set(excludes or [])

    results: List[ConversionTarget] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if allow and not any(str(p).endswith(s) for s in allow):
            # allowlist active: keep only matching suffixes
            continue
        if any(str(p).endswith(s) for s in deny):
            continue
        ext = p.suffix.lower()
        if ext in TS_EXTS:
            continue  # already TS
        if ext not in JS_EXTS:
            continue

        # skip if TS counterpart already exists
        ts_candidate = suggest_ts_filename(p)
        if ts_candidate.exists():
            continue

        kind = "test" if _is_test_file(p) else ("component" if ext == ".jsx" else "module")
        test_target = suggest_test_filename(p)
        results.append(ConversionTarget(src=p, ts_target=ts_candidate, test_target=Path(test_target) if test_target else None, kind=kind))

    return results

