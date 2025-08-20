# === AI-ORCH HEADER ===
# File: core/logger.py
# Purpose: Central logging utility for orchestrator runs.
# Notes: Logs each stage execution to both structured JSON and plain text.

import json
from datetime import datetime
from pathlib import Path

class RunLogger:
    def __init__(self, log_dir="logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        self.text_log = self.log_dir / "orchestrator.log"
        self.json_log = self.log_dir / "orchestrator.jsonl"  # JSON lines

    def log(self, stage: str, content: str, validation: str = "unknown"):
        """Log a stage execution entry."""
        timestamp = datetime.utcnow().isoformat()
        entry = {
            "stage": stage,
            "timestamp": timestamp,
            "content": content,
            "validation": validation,
        }

        # Append JSON entry
        with self.json_log.open("a", encoding="utf-8") as jf:
            jf.write(json.dumps(entry) + "\n")

        # Append text entry
        with self.text_log.open("a", encoding="utf-8") as tf:
            tf.write(f"[{timestamp}] Stage={stage}, Validation={validation}\n")

        return entry
