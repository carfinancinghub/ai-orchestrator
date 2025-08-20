"""
Path: core/ts_validation.py
Run TypeScript compiler and tests, returning structured results that can be folded into orchestrator flags.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import subprocess

from .status import ValidationStatus


@dataclass
class TSCheckResult:
    status: ValidationStatus
    stdout: str
    stderr: str


def run_tsc(tsc_cmd: str, project_root: Path, file_hint: Optional[Path] = None) -> TSCheckResult:
    cmd: List[str] = [tsc_cmd, "--noEmit"]
    if file_hint is not None:
        cmd.append(str(file_hint))
    try:
        proc = subprocess.run(cmd, cwd=str(project_root), capture_output=True, text=True, check=False)
        if proc.returncode == 0:
            return TSCheckResult(ValidationStatus.PASS, proc.stdout, proc.stderr)
        return TSCheckResult(ValidationStatus.FLAG, proc.stdout, proc.stderr)  # FLAG to allow remediation loop
    except FileNotFoundError:
        return TSCheckResult(ValidationStatus.FLAG, "", "tsc-not-found")


@dataclass
class TestRunResult:
    status: ValidationStatus
    stdout: str
    stderr: str


def run_tests(cmd: str, project_root: Path) -> TestRunResult:
    if not cmd:
        return TestRunResult(ValidationStatus.FLAG, "", "test-runner-not-configured")
    try:
        proc = subprocess.run(cmd, cwd=str(project_root), shell=True, capture_output=True, text=True, check=False)
        status = ValidationStatus.PASS if proc.returncode == 0 else ValidationStatus.FLAG
        return TestRunResult(status, proc.stdout, proc.stderr)
    except FileNotFoundError:
        return TestRunResult(ValidationStatus.FLAG, "", "test-runner-cmd-not-found")

