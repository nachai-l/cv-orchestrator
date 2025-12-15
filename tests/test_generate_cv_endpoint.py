# tests/test_generate_cv_endpoint.py

import pytest
from httpx import AsyncClient

from api import app, service
from schemas.output_schema import GenerateCVResponse, GeneratedCV
from schemas.stage0_schema import Language, LanguageTone


@pytest.mark.asyncio
async def test_healthz() -> None:
    """Basic liveness check."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/healthz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "service" in data


@pytest.mark.asyncio
async def test_generate_cv_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy-path test for the orchestrator generate-cv endpoint.

    We monkeypatch OrchestratorService.generate_cv to avoid calling
    real downstream services (data_api, generation service).
    """

    async def fake_generate_cv(request):  # type: ignore[override]
        # Return a minimal but valid GenerateCVResponse
        cv = GeneratedCV(
            job_id="JOB_TEST_123",
            template_id="T_EMPLOYER_STD_V3",
            language=Language.EN,
            language_tone=LanguageTone.FORMAL,
            rendered_html="<html><body>Test CV</body></html>",
            rendered_markdown=None,
            sections=None,
            raw_generation_result={"mock": True},
        )
        return GenerateCVResponse(
            status="success",
            cv=cv,
            error=None,
            user_or_llm_comments=None,
            request_metadata={"test_case": "test_generate_cv_success"},
        )

    # Patch the global service instance used by api.py
    monkeypatch.setattr(service, "generate_cv", fake_generate_cv)

    payload = {
        "student_id": "U-1001",
        "template_id": "T_EMPLOYER_STD_V3",
        "language": "en",
        "language_tone": "formal",
        "sections": ["profile_summary", "skills"],
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post("/v1/orchestrator/generate-cv", json=payload)
        assert resp.status_code == 200

        data = resp.json()
        assert data["status"] == "success"
        assert data["cv"] is not None
        assert data["cv"]["job_id"] == "JOB_TEST_123"
        assert data["cv"]["template_id"] == "T_EMPLOYER_STD_V3"
        assert data["cv"]["rendered_html"].startswith("<html>")
        assert data["error"] is None
