# api.py
"""
FastAPI application entrypoint for the E-port Orchestrator API.

Responsibilities:
- Expose a clean external HTTP API:
    * GET  /healthz
    * GET  /health
    * POST /api/v1/cv-generations        [REST recommended]
    * POST /v1/orchestrator/generate-cv  [Deprecated alias]
- Validate and parse incoming requests using Pydantic schemas.
- Delegate orchestration to OrchestratorService.
- Return a stable, typed response envelope to callers.

Guideline alignment notes:
- Resource-based URL: /api/v1/cv-generations
- HTTP status codes: 201 for create generation
- Standard error format: {code,message,subErrors,timestamp,correlationId}
- Header versioning: X-API-Version supported (default=1)  [URL v1 still primary]
- camelCase JSON: enforced at API boundary via converter
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from functions.orchestrator.eport_orchestrator_service import OrchestratorService
from functions.utils.json_naming_converter import convert_keys_snake_to_camel
from functions.utils.settings import get_settings
from schemas.input_schema import GenerateCVRequest
from schemas.output_schema import GenerateCVResponse

logger = structlog.get_logger(__name__)

settings = get_settings()
service = OrchestratorService()

app = FastAPI(
    title="E-port Orchestrator API",
    version="0.2.0",
    description="Backend-for-Frontend orchestrator for CV generation.",
)

CORRELATION_HEADER = "X-Correlation-Id"
API_VERSION_HEADER = "X-API-Version"
SUPPORTED_API_VERSIONS = {"1"}

# Preserve inner keys for these free-form containers
# (section keys like "profile_summary" must NOT be camelized)
PRESERVE_CONTAINER_KEYS = {
    "user_or_llm_comments",
    "userOrLlmComments",
    "user_input_cv_text_by_section",
    "userInputCvTextBySection",
}


def _get_or_create_correlation_id(request: Request) -> str:
    incoming = request.headers.get(CORRELATION_HEADER)
    return incoming.strip() if incoming else f"corr_{uuid.uuid4().hex}"


def _get_api_version(request: Request) -> str:
    """
    Returns the resolved API version for the request.
    - Prefer request.state.api_version (set by middleware)
    - Fallback to header or default "1"
    """
    v = getattr(request.state, "api_version", None)
    if v:
        return str(v)
    return request.headers.get(API_VERSION_HEADER, "1").strip() or "1"


def _std_error(
    *,
    code: str,
    message: str,
    correlation_id: str,
    http_status: int,
    api_version: str = "1",
    sub_errors: Optional[list[dict[str, Any]]] = None,
) -> JSONResponse:
    payload: dict[str, Any] = {
        "code": code,
        "message": message,
        "subErrors": sub_errors or [],
        "timestamp": int(time.time()),
        "correlationId": correlation_id,
    }
    headers = {
        CORRELATION_HEADER: correlation_id,
        API_VERSION_HEADER: api_version,
    }
    return JSONResponse(status_code=http_status, content=payload, headers=headers)


# -------------------------------------------------------------------
# Middleware order matters: correlation id first, then api versioning
# -------------------------------------------------------------------
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = _get_or_create_correlation_id(request)
    request.state.correlation_id = correlation_id

    response = await call_next(request)
    response.headers[CORRELATION_HEADER] = correlation_id
    return response


@app.middleware("http")
async def api_version_middleware(request: Request, call_next):
    """
    Header versioning support.

    Guideline mentions X-API-Version. We keep URL versioning as primary
    (/api/v1/...) but accept X-API-Version as optional validation/override.
    """
    correlation_id = getattr(request.state, "correlation_id", f"corr_{uuid.uuid4().hex}")
    version = request.headers.get(API_VERSION_HEADER, "1").strip()

    if version not in SUPPORTED_API_VERSIONS:
        # Always include X-API-Version in error response too (default "1")
        return _std_error(
            code="INVALID_FIELD_VALUE",
            message="Invalid API version",
            correlation_id=correlation_id,
            http_status=400,
            api_version="1",
            sub_errors=[
                {
                    "field": API_VERSION_HEADER,
                    "errors": [{"code": "isIn", "message": "Supported versions: 1"}],
                }
            ],
        )

    request.state.api_version = version
    response = await call_next(request)
    response.headers[API_VERSION_HEADER] = version
    return response


# -----------------
# Exception handlers
# -----------------
@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    correlation_id = getattr(request.state, "correlation_id", f"corr_{uuid.uuid4().hex}")
    api_version = _get_api_version(request)

    sub_errors: list[dict[str, Any]] = []
    for err in exc.errors():
        loc = err.get("loc", [])
        field = ".".join([str(x) for x in loc if x != "body"]) or "body"
        sub_errors.append(
            {
                "field": field,
                "errors": [
                    {
                        "code": err.get("type", "validation_error"),
                        "message": err.get("msg", "Invalid value"),
                    }
                ],
            }
        )

    logger.info(
        "request_validation_failed",
        correlation_id=correlation_id,
        error_count=len(sub_errors),
    )

    return _std_error(
        code="VALIDATION_FAILED",
        message="Validation failed",
        correlation_id=correlation_id,
        http_status=400,
        api_version=api_version,
        sub_errors=sub_errors,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    correlation_id = getattr(request.state, "correlation_id", f"corr_{uuid.uuid4().hex}")
    api_version = _get_api_version(request)

    status_to_code = {
        400: "INVALID_REQUEST_FORMAT",
        401: "MISSING_AUTHENTICATION",
        403: "INSUFFICIENT_PERMISSIONS",
        404: "RESOURCE_NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_FAILED",
        429: "RATE_LIMITED",
        500: "INTERNAL_SERVER_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
    }
    code = status_to_code.get(exc.status_code, "HTTP_ERROR")

    logger.warning(
        "http_exception",
        correlation_id=correlation_id,
        status_code=exc.status_code,
        detail=str(exc.detail),
    )

    return _std_error(
        code=code,
        message=str(exc.detail) if exc.detail else "Request failed",
        correlation_id=correlation_id,
        http_status=exc.status_code,
        api_version=api_version,
        sub_errors=[],
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):  # noqa: BLE001
    correlation_id = getattr(request.state, "correlation_id", f"corr_{uuid.uuid4().hex}")
    api_version = _get_api_version(request)

    logger.error(
        "unhandled_exception",
        correlation_id=correlation_id,
        error=str(exc),
    )

    return _std_error(
        code="INTERNAL_SERVER_ERROR",
        message="Unexpected error while processing request.",
        correlation_id=correlation_id,
        http_status=500,
        api_version=api_version,
        sub_errors=[],
    )


# ---------
# Endpoints
# ---------
@app.get("/healthz", summary="Liveness probe")
async def healthz() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.service_name,
        "environment": settings.environment,
    }


@app.get("/health", summary="Liveness probe (alias)")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.service_name,
        "environment": settings.environment,
    }


# -------------------------
# REST recommended endpoint
# -------------------------
@app.post(
    "/api/v1/cv-generations",
    response_model=GenerateCVResponse,
    summary="Create a CV generation (REST resource)",
    status_code=201,
)
async def create_cv_generation(payload: GenerateCVRequest) -> JSONResponse:
    """
    REST guideline aligned endpoint.

    camelCase JSON is enforced at the response boundary.
    - structural keys: snake_case -> camelCase
    - free-form section containers: keep inner keys unchanged (e.g. "profile_summary")
    """
    result = await service.generate_cv(payload)
    payload_dict = convert_keys_snake_to_camel(
        result.model_dump(),
        preserve_container_keys=PRESERVE_CONTAINER_KEYS,
    )
    return JSONResponse(status_code=201, content=payload_dict)


# --------------------------------
# Backward-compatible deprecated API
# --------------------------------
@app.post(
    "/v1/orchestrator/generate-cv",
    response_model=GenerateCVResponse,
    summary="Generate CV (Deprecated alias; use POST /api/v1/cv-generations)",
)
async def generate_cv_endpoint(payload: GenerateCVRequest) -> JSONResponse:
    """
    Deprecated alias for compatibility.
    """
    result = await service.generate_cv(payload)
    payload_dict = convert_keys_snake_to_camel(
        result.model_dump(),
        preserve_container_keys=PRESERVE_CONTAINER_KEYS,
    )
    return JSONResponse(status_code=200, content=payload_dict)
