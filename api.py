# app.py
"""
FastAPI application entrypoint for the E-port Orchestrator API.

Responsibilities:
- Expose a clean external HTTP API:
    * GET  /healthz
    * GET  /health
    * POST /v1/orchestrator/generate-cv
- Validate and parse incoming requests using Pydantic schemas.
- Delegate orchestration to OrchestratorService.
- Return a stable, typed response envelope to callers.
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from functions.orchestrator.eport_orchestrator_service import OrchestratorService
from functions.utils.settings import get_settings
from schemas.input_schema import GenerateCVRequest
from schemas.output_schema import GenerateCVError, GenerateCVResponse

logger = structlog.get_logger(__name__)

settings = get_settings()
service = OrchestratorService()

app = FastAPI(
    title="E-port Orchestrator API",
    version="0.1.0",
    description="Backend-for-Frontend orchestrator for CV generation.",
)


@app.get("/healthz", summary="Liveness probe")
async def healthz() -> dict[str, str]:
    """
    Simple health endpoint used by Cloud Run / monitoring.

    Does not perform deep dependency checks; it only indicates that the
    API process is up and running.
    """
    return {
        "status": "ok",
        "service": settings.service_name,
        "environment": settings.environment,
    }


@app.get("/health", summary="Liveness probe (alias)")
async def health() -> dict[str, str]:
    """
    Alias for /healthz, provided for convenience and compatibility with
    generic health check tooling.
    """
    return {
        "status": "ok",
        "service": settings.service_name,
        "environment": settings.environment,
    }


@app.post(
    "/v1/orchestrator/generate-cv",
    response_model=GenerateCVResponse,
    summary="Generate CV via orchestrated data + generation service",
)
async def generate_cv_endpoint(payload: GenerateCVRequest) -> JSONResponse:
    """
    Main orchestration endpoint.

    - Validates the external request.
    - Orchestrates data fetching + CV generation.
    - Returns a standardized response envelope.
    """
    try:
        result = await service.generate_cv(payload)
        # result is already a GenerateCVResponse instance
        return JSONResponse(status_code=200, content=result.model_dump())

    except HTTPException as exc:
        # Allow explicit HTTPExceptions to propagate as-is
        logger.warning(
            "generate_cv_http_exception",
            status_code=exc.status_code,
            detail=str(exc.detail),
        )
        raise

    except Exception as exc:  # noqa: BLE001
        logger.error("generate_cv_unhandled_exception", error=str(exc))
        error = GenerateCVError(
            code="ORCH_INTERNAL_ERROR",
            message="Unexpected error while processing CV generation request.",
            details={"reason": str(exc)},
        )
        resp = GenerateCVResponse(
            status="error",
            cv=None,
            error=error,
            user_or_llm_comments=None,
            request_metadata=None,
        )
        return JSONResponse(status_code=500, content=resp.model_dump())
