# app/utils/numeric_junk.py
from pathlib import Path
import os
import re
from typing import Iterable

_DIGIT_RUN = int(os.getenv("AIO_NUMERIC_JUNK_DIGITS", "3"))
_ALLOWLIST = {s.strip().lower() for s in os.getenv("AIO_NUMERIC_ALLOWLIST", "").split(",") if s.strip()}

def is_numeric_junk(path: str) -> bool:
    stem = Path(path).stem.lower()
    if stem in _ALLOWLIST:
        return False
    if re.fullmatch(r"[\d\W]+", stem):
        return True
    if re.search(rf"\d{{{_DIGIT_RUN},}}", stem):
        return True
    return False

def filter_non_junk(paths: Iterable[str]) -> Iterable[str]:
    for p in paths:
        if not is_numeric_junk(p):
            yield p
