""" Path: tests/test_orchestrator_echo.py """

from pathlib import Path
from core.orchestrator import Orchestrator, OrchestratorConfig


def test_generate_writes_echo_first_line(tmp_path):
o = Orchestrator(OrchestratorConfig(base_dir=tmp_path, reports_dir=tmp_path / "reports"))
res = o.run_stage("generate")
p = Path(res["artifact_file"])
line0 = p.read_text(encoding="utf-8").splitlines()[0]