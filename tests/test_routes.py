# === AI-ORCH TESTS HEADER ===
# File: tests/test_routes.py
# Purpose: Automated tests for Orchestrator endpoints.
# Notes:
#   - Validates stage execution, artifact creation, and health/status endpoints.
#   - Runs pre-validation on artifacts to filter junk, flag mismatches, or confirm pass.

import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport

from app.server import app
from core.artifact_validator import ArtifactValidator, ValidationResult

# --- Setup ---
validator = ArtifactValidator()
transport = ASGITransport(app=app)


# --- Health + Status Tests ---

@pytest.mark.asyncio
async def test_root_health():
    """Check root endpoint returns message."""
    async with AsyncClient(base_url="http://test", transport=transport) as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert response.json().get("message") == "AI Orchestrator is running!"


@pytest.mark.asyncio
async def test_orchestrator_status():
    """Check orchestrator status endpoint."""
    async with AsyncClient(base_url="http://test", transport=transport) as client:
        response = await client.get("/orchestrator/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


# --- Stage Execution + Artifact Validation ---

@pytest.mark.asyncio
async def test_run_all_stages_with_validation():
    """
    Trigger all orchestrator stages sequentially.
    Validate each artifact with ArtifactValidator:
      - PASS → continue
      - FLAG → log warning but allow
      - FAIL → fail test
    """
    stages = ["generate", "qa", "review", "evaluate", "persist"]

    async with AsyncClient(base_url="http://test", transport=transport) as client:
        for stage in stages:
            response = await client.post(f"/orchestrator/run-stage/{stage}")
            assert response.status_code == 200

            artifact_file = response.json().get("artifact_file")
            assert artifact_file is not None

            artifact_path = Path(artifact_file)
            result = validator.validate(artifact_path, expected_stage=stage)

            if result == ValidationResult.FAIL:
                pytest.fail(f"❌ Artifact for stage '{stage}' failed validation: {artifact_file}")
            elif result == ValidationResult.FLAG:
                print(f"⚠️ Artifact for stage '{stage}' flagged for manual review: {artifact_file}")
            else:
                print(f"✅ Artifact for stage '{stage}' passed validation: {artifact_file}")


# --- Artifact Retrieval ---

@pytest.mark.asyncio
async def test_artifact_retrieval():
    """Retrieve latest artifact for a stage and validate its content."""
    stage = "generate"
    async with AsyncClient(base_url="http://test", transport=transport) as client:
        # Ensure artifact exists first
        run_response = await client.post(f"/orchestrator/run-stage/{stage}")
        assert run_response.status_code == 200

        # Retrieve latest artifact
        response = await client.get(f"/orchestrator/artifacts/{stage}")
        assert response.status_code == 200
        data = response.json()

        artifact_file = data.get("artifact_file")
        content = data.get("content")

        assert artifact_file is not None
        assert content is not None
        assert stage in content

        # Run validator on retrieved artifact file
        artifact_path = Path(artifact_file)
        result = validator.validate(artifact_path, expected_stage=stage)
        assert result in (ValidationResult.PASS, ValidationResult.FLAG), \
            f"❌ Retrieved artifact for stage '{stage}' failed validation"
