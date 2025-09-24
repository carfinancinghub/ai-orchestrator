from __future__ import annotations
import os
from pathlib import Path

_DEFAULT_SKIP = {
    "node_modules","public","build","dist","coverage","storybook-static",
    ".git",".next",".turbo",".yarn",".pnpm-store",".cache","out",
}

def get_skip_dirs() -> set[str]:
    raw = os.getenv("AIO_SKIP_DIRS","")
    items = {x.strip() for x in raw.split(",") if x.strip()}
    return {s.casefold() for s in (items or _DEFAULT_SKIP)}

def is_skipped(path: Path) -> bool:
    try:
        parts = [p.casefold() for p in path.parts]
    except Exception:
        parts = []
    skip = get_skip_dirs()
    return path.is_symlink() or any(seg in skip for seg in parts)
