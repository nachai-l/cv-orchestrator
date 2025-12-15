"""
Input schema definitions for the Orchestrator API.

This is the *external* request contract for:
    POST /v1/orchestrator/generate-cv

Design goals:
- Thin wrapper around identifiers (student_id, role_id, jd_id, template_id)
- Allow optional user overrides and free-form comments
- Orchestrator fetches full profiles and assembles Stage-0 internally
"""

from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field, field_validator

from .stage0_schema import Language, LanguageTone


# ---------------------------------------------------------------------------
# Main External Request Schema
# ---------------------------------------------------------------------------

SectionsLiteral = Literal[
    "profile_summary",
    "skills",
    "experience",
    "education",
    "projects",
    "certifications",
    "awards",
    "extracurricular",
    "volunteering",
    "interests",
    "publications",
    "training",
    "references",
    "additional_info",
]


class GenerateCVRequest(BaseModel):
    """
    External request schema for the Orchestrator API.

    Orchestrator responsibilities:
    - Fetch full student/role/JD/template data
    - Build Stage-0 payload (eport_generation input)
    - Call generation API
    """

    # --------------------------
    # Identifiers for hydration
    # --------------------------
    student_id: str = Field(
        ...,
        pattern=r"^[A-Za-z0-9_-]+$",
        max_length=50,
        description="Platform student ID, e.g. U-1001",
    )

    role_id: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Optional role taxonomy ID, e.g. role#ai_engineer",
    )

    jd_id: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Optional JD taxonomy ID, e.g. jd#ai_lead_gov_2025",
    )

    template_id: str = Field(
        default="T_EMPLOYER_STD_V3",
        pattern=r"^T_[A-Z_]+_V\d+$",
        description="Template ID for CV layout",
    )

    # --------------------------
    # Generation controls
    # --------------------------
    language: Language = Field(
        default=Language.EN,
        description="Output language for generated CV",
    )

    language_tone: LanguageTone = Field(
        default=LanguageTone.FORMAL,
        description="Tone style for generated CV",
    )

    sections: list[SectionsLiteral] = Field(
        default=[
            "profile_summary",
            "skills",
            "experience",
            "education",
            "awards",
            "extracurricular",
        ],
        min_length=1,
        max_length=10,
        description="Which CV sections to generate",
    )

    # --------------------------
    # User-provided optional fields
    # --------------------------

    # NOTE: Must be dict[str, Any], NOT typed model.
    # This allows user-defined shapes that match the generation input schema.
    user_input_cv_text_by_section: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Optional per-section user overrides. "
            "Orchestrator passes this through directly to Stage-0."
        ),
    )

    # NOTE: Free-form dict passthrough. Simpler than UserOrLLMComments model.
    user_or_llm_comments: Optional[Dict[str, str]] = Field(
        default=None,
        description=(
            "Free-form comments keyed by section. "
            "Passed through end-to-end without modification."
        ),
    )

    # --------------------------
    # Request metadata
    # --------------------------
    request_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata (channel, correlation ID, etc.)",
    )

    model_config = {"extra": "forbid"}

    @field_validator("sections")
    @classmethod
    def deduplicate_sections(cls, sections: list[str]) -> list[str]:
        """Ensure sections are unique while preserving order."""
        seen: set[str] = set()
        result: list[str] = []
        for s in sections:
            if s not in seen:
                seen.add(s)
                result.append(s)
        return result
