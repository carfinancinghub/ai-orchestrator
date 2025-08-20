"""
Path: core/orchestrator.py
Minimal Orchestrator used by routes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import os

@dataclass
class OrchestratorConfig:
    base_dir: Path = Path("./artifacts")
    reports_dir: Path = Path("./reports")

@dataclass
class Orchestrator:
    config: OrchestratorConfig = field(default_factory=OrchestratorConfig)
    stages: List[str] = field(default_factory=lambda: ["generate","qa","review","evaluate","persist"])

    def __post_init__(self) -> None:
        self.config.base_dir.mkdir(parents=True, exist_ok=True)
        self.config.reports_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
        self.completed: List[str] = []
        self.settings: Dict[str, object] = {
            "DRY_RUN": os.getenv("AIO_DRY_RUN", "true").strip().lower() in {"1","true","yes","on"}
        }

    # accessors
    def get_completed_stages(self) -> List[str]:
        return list(self.completed)

    def get_run_id(self) -> str:
        return self.run_id

    # pipeline
    def run_stage(self, stage: str) -> Dict[str, object]:
        stage = stage.lower()
        if stage not in self.stages:
            raise ValueError(f"unknown-stage:{stage}")
        content = (
            f"Run-ID: {self.run_id}\n"
            f"Stage: {stage}\n"
            f"Timestamp: {datetime.now(timezone.utc).isoformat()}\n"
        )
        p = self._write_artifact(stage, content)
        self.completed.append(stage)
        return {"stage": stage, "status": "OK", "artifact_file": str(p), "stopped": False}

    def run_all(self) -> Dict[str, object]:
        last = None
        for s in self.stages:
            last = self.run_stage(s)
        return {"run_id": self.run_id, "completed": self.get_completed_stages(), "last": last}

    # JS→TS helpers
    def discover_conversion(self, root: Path) -> List[Dict[str, str]]:
        root = Path(root)
        items: List[Dict[str, str]] = []
        skip = {"node_modules", ".git", "venv", ".pytest_cache"}
        for pat in ("**/*.js", "**/*.jsx"):
            for src in root.glob(pat):
                if any(part in skip for part in src.parts):
                    continue
                ts = src.with_suffix(".tsx" if src.suffix.lower() == ".jsx" else ".ts")
                items.append({
                    "src": str(src.resolve()),
                    "ts_target": str(ts.resolve()),
                    "test_target": "",
                    "kind": "module",
                })
        return items

    def convert_file(
        self, src: Path, write_to_repo: bool = False, include_tests: bool = True, force_write: bool = False
    ) -> Dict[str, object]:
        src = Path(src)
        if not src.exists():
            return {"ok": False, "reason": "missing"}
        ts_path = src.with_suffix(".tsx" if src.suffix.lower() == ".jsx" else ".ts")
        header = f"// Converted from {src.name} — {datetime.now(timezone.utc).isoformat()}\n"
        ts_code = header + src.read_text(encoding="utf-8", errors="replace")
        wrote = None
        dry_run = bool(self.settings.get("DRY_RUN", True))
        if write_to_repo and (force_write or not dry_run):
            ts_path.parent.mkdir(parents=True, exist_ok=True)
            ts_path.write_text(ts_code, encoding="utf-8")
            wrote = ts_path
            if include_tests:
                test_path = ts_path.with_name(
                    ts_path.stem + ".test" + (".tsx" if ts_path.suffix.lower() == ".tsx" else ".ts")
                )
                if not test_path.exists():
                    test_path.write_text(f"// Auto test scaffold for {ts_path.name}\n", encoding="utf-8")
        art = self._write_artifact("convert", f"Conversion: {src} -> {ts_path}\nWrote: {wrote is not None}\n")
        return {"ok": True, "artifact": str(art), "ts_path": (str(wrote) if wrote else None)}

    # helpers
    def _write_artifact(self, stage: str, content: str) -> Path:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        p = self.config.base_dir / f"{stage}_{ts}.txt"
        p.write_text(content, encoding="utf-8")
        return p
