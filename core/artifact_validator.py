"""
Path: core/artifact_validator.py
Artifact validation heuristics + quarantine handling.

Back-compat:
- `validate(path, expected_stage)` returns a `ValidationStatus` enum.
- `validate_file(...)` returns a structured ValidationResult.
"""
from __future__ import annotations
import logging
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .status import ValidationStatus, ValidationResult


@dataclass
class ArtifactValidator:
    allowed_stages: Iterable[str] = ("generate", "qa", "review", "evaluate", "persist")
    max_size_bytes: int = 100_000
    quarantine_dir: Optional[Path] = Path("./artifacts_quarantine")
    junk_patterns: List[re.Pattern] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.junk_patterns:
            self.junk_patterns = [
                re.compile(r"lorem\s+ipsum", re.I),
                re.compile(r"\b(dummy|placeholder|TBD|TODO)\b", re.I),
                re.compile(r"[A-Za-z0-9+/]{200,}={0,2}"),
                re.compile(r"[!?.]{8,}"),
            ]
        if self.quarantine_dir:
            Path(self.quarantine_dir).mkdir(parents=True, exist_ok=True)

    # Back-compat alias expected by tests: return enum status
    def validate(self, path: Path, expected_stage: Optional[str] = None) -> ValidationStatus:
        res = self.validate_file(path, expected_stage)
        return res.status

    def validate_file(self, path: Path, expected_stage: Optional[str] = None) -> ValidationResult:
        path = Path(path)
        reasons: List[str] = []
        # existence/size
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            return ValidationResult(path, expected_stage, ValidationStatus.FAIL, ["file-missing"], False)
        if size == 0:
            return self._fail(path, expected_stage, ["empty-file"], quarantine=True)
        if size > self.max_size_bytes:
            return self._fail(path, expected_stage, [f"oversize:{size}>{self.max_size_bytes}"], quarantine=True)
        # encoding
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return self._fail(path, expected_stage, ["non-utf8/binary"], quarantine=True)
        # headers
        headers = self._parse_headers(text)
        required = {"Run-ID", "Artifact-ID", "Stage", "Version", "Timestamp"}
        missing = sorted(h for h in required if h not in headers)
        if missing:
            reasons.append(f"missing-headers:{','.join(missing)}")
        header_stage = headers.get("Stage")
        inferred_stage = header_stage or self._infer_stage_from_filename(path)
        if expected_stage and inferred_stage and expected_stage != inferred_stage:
            reasons.append(f"stage-mismatch expected={expected_stage} found={inferred_stage}")
        elif expected_stage and not inferred_stage:
            reasons.append("stage-unknown")
        # junk/code
        junk_hits = sum(1 for p in self.junk_patterns if p.search(text))
        if junk_hits >= 2:
            return self._fail(path, expected_stage or inferred_stage, ["junk-content"], quarantine=True)
        elif junk_hits == 1:
            reasons.append("junk-suspected")
        if self._looks_like_code(text) and (expected_stage not in ("review", "evaluate", "persist")):
            reasons.append("code-like-content")
        status = ValidationStatus.PASS if not reasons else ValidationStatus.FLAG
        return ValidationResult(path, expected_stage or inferred_stage, status, reasons, False)

    # helpers
    def _fail(self, path: Path, stage: Optional[str], reasons: List[str], quarantine: bool = False) -> ValidationResult:
        quarantined = False
        if quarantine and self.quarantine_dir:
            try:
                target = Path(self.quarantine_dir) / path.name
                shutil.move(str(path), target)
                path = target
                quarantined = True
            except Exception as exc:  # pragma: no cover
                logging.getLogger(__name__).warning("quarantine-move-failed: %s", exc)
        return ValidationResult(path, stage, ValidationStatus.FAIL, reasons, quarantined)

    @staticmethod
    def _parse_headers(text: str) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        for line in text.splitlines()[:20]:
            if ":" in line:
                k, v = line.split(":", 1)
                k, v = k.strip(), v.strip()
                if k and v:
                    headers[k] = v
        return headers

    @staticmethod
    def _looks_like_code(text: str) -> bool:
        pats = [r"\bdef\s+\w+\s*\(", r"\bclass\s+\w+\s*[:{]", r"#include\s*<", r"\bimport\s+\w+", r"\bfunction\s+\w+\s*\("]
        return sum(1 for p in pats if re.search(p, text)) >= 2

    @staticmethod
    def _infer_stage_from_filename(path: Path) -> Optional[str]:
        name = path.name.lower()
        for stage in ("generate", "qa", "review", "evaluate", "persist"):
            if name.startswith(stage + "_") or f"_{stage}_" in name:
                return stage
        return None

