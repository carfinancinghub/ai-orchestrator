"""
Path: core/status.py
Shared status enums and dataclasses for validations and scans.
Back-compat: expose ValidationResult.PASS/FLAG/FAIL as class vars for tests
that compare against these constants directly.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import ClassVar, Dict, List, Optional


class ValidationStatus(str, Enum):
    PASS = "PASS"
    FLAG = "FLAG"
    FAIL = "FAIL"


@dataclass
class ValidationResult:
    # Back-compat constants so tests can use ValidationResult.PASS, etc.
    PASS: ClassVar[ValidationStatus] = ValidationStatus.PASS
    FLAG: ClassVar[ValidationStatus] = ValidationStatus.FLAG
    FAIL: ClassVar[ValidationStatus] = ValidationStatus.FAIL

    filepath: Path
    stage: Optional[str]
    status: ValidationStatus
    reasons: List[str] = field(default_factory=list)
    quarantined: bool = False

    def to_dict(self) -> Dict[str, object]:
        return {
            "filepath": str(self.filepath),
            "stage": self.stage,
            "status": self.status.value,
            "reasons": list(self.reasons),
            "quarantined": self.quarantined,
        }


@dataclass
class ScanSummary:
    counts: Dict[str, int]
    results: List[ValidationResult]

    def to_dict(self) -> Dict[str, object]:
        return {
            "PASS": self.counts.get("PASS", 0),
            "FLAG": self.counts.get("FLAG", 0),
            "FAIL": self.counts.get("FAIL", 0),
            "results": [r.to_dict() for r in self.results],
        }

