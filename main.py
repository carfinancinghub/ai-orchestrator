# main.py
# Entry point for AI Orchestrator

from core.orchestrator import Orchestrator
from datetime import datetime
import os

def bootstrap():
    orchestrator = Orchestrator()
    print("Orchestrator mock initialized")

    # Ensure archive folder exists
    os.makedirs("archive", exist_ok=True)

    # Run all stages
    for stage in ["generate", "qa", "review", "evaluate", "persist"]:
        artifact_name = f"{stage}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        artifact_path = os.path.join("archive", artifact_name)

        # Simulate stage execution
        print(f"Running stage: {stage} -> saving artifact: {artifact_name}")
        with open(artifact_path, "w", encoding="utf-8") as f:
            f.write("({[\n")
            f.write(f"{stage.upper()} ARTIFACT\n")
            f.write(f"This is a mock artifact for stage: {stage}\n")
            f.write(f"Timestamp: {datetime.now()}\n")
            f.write("({]})\n")

    print("Bootstrap mock executed")
    print("🚀 Orchestrator ready at http://127.0.0.1:8000")

if __name__ == "__main__":
    bootstrap()
