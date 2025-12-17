import re

import httpx
import pytest

import api as app_module


# -------------------------
# Test client helper
# -------------------------
def _client(*, raise_app_exceptions: bool = True):
    """
    ASGI test client.

    - raise_app_exceptions=True  (default):
        Fast-fail on server exceptions (useful for most tests)
    - raise_app_exceptions=False:
        Return HTTP 500 responses instead of raising (needed for error-handling tests)
    """
    transport = httpx.ASGITransport(
        app=app_module.app,
        raise_app_exceptions=raise_app_exceptions,
    )
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# -------------------------
# Health checks
# -------------------------
@pytest.mark.asyncio
async def test_healthz_ok():
    async with _client() as ac:
        r = await ac.get("/healthz")

    assert r.status_code == 200
    # Middlewares should still attach headers even on simple endpoints
    assert r.headers.get("X-Correlation-Id")
    assert r.headers.get("X-API-Version") == "1"

    data = r.json()
    assert data["status"] == "ok"
    assert "service" in data
    assert "environment" in data


# -------------------------
# REST endpoint (snake_case request)
# -------------------------
@pytest.mark.asyncio
async def test_create_cv_generation_returns_201_and_sets_correlation_id(monkeypatch):
    async def fake_generate_cv(payload):
        # Return internal model (snake_case keys). API converts response to camelCase.
        return app_module.GenerateCVResponse(
            status="success",
            cv={
                "job_id": "JOB_U-1001",
                "template_id": payload.template_id,
                "language": payload.language,
                "language_tone": payload.language_tone,
                "rendered_html": None,
                "rendered_markdown": None,
                "sections": {},
                "raw_generation_result": {"status": "completed"},
            },
            error=None,
            user_or_llm_comments=payload.user_or_llm_comments,
            request_metadata=payload.request_metadata,
        )

    monkeypatch.setattr(app_module.service, "generate_cv", fake_generate_cv)

    req = {
        "student_id": "U-1001",
        "template_id": "T_EMPLOYER_STD_V3",
        "language": "th",
        "language_tone": "formal",
        "sections": ["profile_summary"],
        "user_or_llm_comments": {"profile_summary": "test"},
        "request_metadata": {"source": "pytest"},
    }

    async with _client() as ac:
        r = await ac.post("/api/v1/cv-generations", json=req)

    assert r.status_code == 201
    assert r.headers.get("X-Correlation-Id")
    assert r.headers.get("X-API-Version") == "1"

    body = r.json()
    assert body["status"] == "success"

    # ✅ camelCase conversion check (top-level)
    assert "userOrLlmComments" in body
    assert "requestMetadata" in body

    # ✅ camelCase conversion check (cv)
    assert body["cv"]["jobId"] == "JOB_U-1001"
    assert "templateId" in body["cv"]
    assert "languageTone" in body["cv"]
    assert "renderedHtml" in body["cv"]
    assert "renderedMarkdown" in body["cv"]
    assert "rawGenerationResult" in body["cv"]


# -------------------------
# REST endpoint (camelCase request should be accepted)
# -------------------------
@pytest.mark.asyncio
async def test_create_cv_generation_accepts_camelcase_request(monkeypatch):
    async def fake_generate_cv(payload):
        return app_module.GenerateCVResponse(
            status="success",
            cv={
                "job_id": "JOB_U-2001",
                "template_id": payload.template_id,
                "language": payload.language,
                "language_tone": payload.language_tone,
                "rendered_html": None,
                "rendered_markdown": None,
                "sections": {},
                "raw_generation_result": {"status": "completed"},
            },
            error=None,
            user_or_llm_comments=payload.user_or_llm_comments,
            request_metadata=payload.request_metadata,
        )

    monkeypatch.setattr(app_module.service, "generate_cv", fake_generate_cv)

    req = {
        "studentId": "U-2001",
        "templateId": "T_EMPLOYER_STD_V3",
        "language": "en",
        "languageTone": "neutral",
        "sections": ["profile_summary"],
        "userOrLlmComments": {"profile_summary": "camelCase input"},
        "requestMetadata": {"source": "pytest"},
    }

    async with _client() as ac:
        r = await ac.post("/api/v1/cv-generations", json=req)

    assert r.status_code == 201
    assert r.headers.get("X-Correlation-Id")
    assert r.headers.get("X-API-Version") == "1"

    body = r.json()
    assert body["cv"]["jobId"] == "JOB_U-2001"
    assert body["userOrLlmComments"]["profile_summary"] == "camelCase input"
    assert body["requestMetadata"]["source"] == "pytest"

# -------------------------
# Validation errors
# -------------------------
@pytest.mark.asyncio
async def test_validation_error_returns_guideline_error_schema():
    bad_req = {"language": "en"}  # missing required fields

    async with _client() as ac:
        r = await ac.post("/api/v1/cv-generations", json=bad_req)

    assert r.status_code == 400
    assert r.headers.get("X-Correlation-Id")
    assert r.headers.get("X-API-Version") == "1"

    body = r.json()
    assert body["code"] == "VALIDATION_FAILED"
    assert body["message"] == "Validation failed"
    assert isinstance(body["subErrors"], list)
    assert isinstance(body["timestamp"], int)
    assert isinstance(body["correlationId"], str)
    assert re.match(r"^corr_[0-9a-f]+$", body["correlationId"])


# -------------------------
# Deprecated alias endpoint
# -------------------------
@pytest.mark.asyncio
async def test_deprecated_generate_cv_alias_returns_200(monkeypatch):
    async def fake_generate_cv(payload):
        return app_module.GenerateCVResponse(
            status="success",
            cv={
                "job_id": "JOB_U-1002",
                "template_id": payload.template_id,
                "language": payload.language,
                "language_tone": payload.language_tone,
                "rendered_html": None,
                "rendered_markdown": None,
                "sections": {},
                "raw_generation_result": {"status": "completed"},
            },
            error=None,
            user_or_llm_comments=None,
            request_metadata=None,
        )

    monkeypatch.setattr(app_module.service, "generate_cv", fake_generate_cv)

    req = {
        "student_id": "U-1002",
        "template_id": "T_EMPLOYER_STD_V3",
        "language": "en",
        "language_tone": "neutral",
        "sections": ["profile_summary"],
    }

    async with _client() as ac:
        r = await ac.post("/v1/orchestrator/generate-cv", json=req)

    assert r.status_code == 200
    assert r.headers.get("X-Correlation-Id")
    assert r.headers.get("X-API-Version") == "1"

    body = r.json()
    assert body["status"] == "success"
    assert body["cv"]["jobId"] == "JOB_U-1002"
    assert "rawGenerationResult" in body["cv"]


# -------------------------
# Correlation ID passthrough
# -------------------------
@pytest.mark.asyncio
async def test_passthrough_correlation_id_header(monkeypatch):
    async def fake_generate_cv(payload):
        return app_module.GenerateCVResponse(
            status="success",
            cv={
                "job_id": "JOB_U-1003",
                "template_id": payload.template_id,
                "language": payload.language,
                "language_tone": payload.language_tone,
                "rendered_html": None,
                "rendered_markdown": None,
                "sections": {},
                "raw_generation_result": {"status": "completed"},
            },
            error=None,
            user_or_llm_comments=None,
            request_metadata=None,
        )

    monkeypatch.setattr(app_module.service, "generate_cv", fake_generate_cv)

    req = {
        "student_id": "U-1003",
        "template_id": "T_EMPLOYER_STD_V3",
        "language": "en",
        "language_tone": "neutral",
        "sections": ["profile_summary"],
    }

    corr = "abc123def456"

    async with _client() as ac:
        r = await ac.post(
            "/api/v1/cv-generations",
            json=req,
            headers={"X-Correlation-Id": corr},
        )

    assert r.status_code == 201
    assert r.headers.get("X-Correlation-Id") == corr
    assert r.headers.get("X-API-Version") == "1"


# -------------------------
# Unhandled exception → 500
# -------------------------
@pytest.mark.asyncio
async def test_unhandled_exception_returns_500_standard_error(monkeypatch):
    async def boom(_payload):
        raise RuntimeError("boom")

    monkeypatch.setattr(app_module.service, "generate_cv", boom)

    req = {
        "student_id": "U-1001",
        "template_id": "T_EMPLOYER_STD_V3",
        "language": "en",
        "language_tone": "neutral",
        "sections": ["profile_summary"],
    }

    async with _client(raise_app_exceptions=False) as ac:
        r = await ac.post("/api/v1/cv-generations", json=req)

    assert r.status_code == 500
    assert r.headers.get("X-Correlation-Id")
    assert r.headers.get("X-API-Version") == "1"

    body = r.json()
    assert body["code"] == "INTERNAL_SERVER_ERROR"
    assert body["message"] == "Unexpected error while processing request."
    assert isinstance(body["timestamp"], int)
    assert isinstance(body["correlationId"], str)
    assert re.match(r"^corr_[0-9a-f]+$", body["correlationId"])


# -------------------------
# API versioning
# -------------------------
@pytest.mark.asyncio
async def test_invalid_api_version_returns_400():
    async with _client() as ac:
        r = await ac.post(
            "/api/v1/cv-generations",
            json={"language": "en"},
            headers={"X-API-Version": "2"},
        )

    assert r.status_code == 400
    assert r.headers.get("X-Correlation-Id")

    body = r.json()
    assert body["code"] == "INVALID_FIELD_VALUE"
    assert body["message"] == "Invalid API version"
    assert "subErrors" in body
    assert body["subErrors"][0]["field"] == "X-API-Version"
