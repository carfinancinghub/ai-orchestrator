from pathlib import Path
from core.orchestrator import Orchestrator, OrchestratorConfig

def test_generate_writes_echo_first_line(tmp_path: Path):
    o = Orchestrator(OrchestratorConfig(base_dir=tmp_path, reports_dir=tmp_path / "reports"))
    res = o.run_stage("generate")
    line0 = Path(res["artifact_file"]).read_text(encoding="utf-8").splitlines()[0]
    assert line0.startswith("ECHO: ")
