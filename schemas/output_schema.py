"""
Output schema definitions for the Orchestrator API.

This is the *external* response contract for:
    POST /v1/orchestrator/generate-cv

Design goals:
- Clean, consumer-friendly envelope (status + result + error).
- Do NOT leak raw internal fields unnecessarily.
- Still allow full Stage-D JSON from eport_generation to be exposed
  under a metadata field when needed.
"""

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

from .stage0_schema import Language, LanguageTone


# ---------------------------------------------------------------------------
# Error Envelope
# ---------------------------------------------------------------------------
class GenerateCVError(BaseModel):
    """
    Standard error envelope for the orchestrator.

    `code` should be a short, machine-readable string, e.g.:
        - "ORCH_DATA_API_ERROR"
        - "ORCH_GENERATION_TIMEOUT"
        - "ORCH_INTERNAL_ERROR"

    `message` is human-readable.
    `details` is optional debug context safe for client use.
    """

    code: str = Field(..., max_length=100)
    message: str = Field(..., max_length=1000)
    details: Optional[Dict[str, Any]] = None

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Generated CV Structure
# ---------------------------------------------------------------------------
class GeneratedCV(BaseModel):
    """
    High-level representation of the generated CV.

    Included when `status == "success"`.
    """

    job_id: Optional[str] = Field(
        default=None,
        description="Job/correlation ID from generation service.",
    )
    template_id: Optional[str] = Field(
        default=None,
        description="Template ID used by the generation engine.",
    )

    language: Optional[Language] = None
    language_tone: Optional[LanguageTone] = None

    rendered_html: Optional[str] = None
    rendered_markdown: Optional[str] = None

    sections: Optional[Dict[str, Any]] = None

    raw_generation_result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Full JSON returned by Stage D of eport_generation.",
    )

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Main Response Envelope
# ---------------------------------------------------------------------------
class GenerateCVResponse(BaseModel):
    """
    Top-level response envelope for:

        POST /v1/orchestrator/generate-cv

    Behavior:
        - When status="success": `cv` is filled, `error` is None.
        - When status="error":   `error` is filled, `cv` is None.

    Optional passthrough:
        - user_or_llm_comments: dict[str, str] | None
        - request_metadata: any caller metadata echoed back
    """

    status: Literal["success", "error"]

    cv: Optional[GeneratedCV] = None
    error: Optional[GenerateCVError] = None

    # NEW simplified passthrough type — aligned with input_schema
    user_or_llm_comments: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional user/LLM comments preserved end-to-end.",
    )

    request_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata echoed or augmented by the orchestrator.",
    )

    model_config = {"extra": "forbid"}
