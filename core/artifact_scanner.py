"""
Path: core/artifact_scanner.py
Bulk scanning of artifacts using ArtifactValidator.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional, List, Dict

from .status import ValidationResult, ScanSummary
from .artifact_validator import ArtifactValidator


class ArtifactScanner:
    def __init__(self, validator: ArtifactValidator) -> None:
        self.validator = validator

    def scan_file(self, path: Path, stage: Optional[str] = None) -> ValidationResult:
        return self.validator.validate_file(Path(path), expected_stage=stage)

    def scan_dir(self, directory: Path, stage: Optional[str] = None) -> ScanSummary:
        directory = Path(directory)
        results: List[ValidationResult] = []
        counts: Dict[str, int] = {"PASS": 0, "FLAG": 0, "FAIL": 0}
        if not directory.exists():
            return ScanSummary(counts, results)
        for p in directory.rglob("*.txt"):
            if p.is_file():
                res = self.scan_file(p, stage)
                results.append(res)
                counts[res.status.value] += 1
        return ScanSummary(counts, results)