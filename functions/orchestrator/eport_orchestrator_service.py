# eport_orchestrator_service.py
"""
Core orchestration logic for CV generation.

Responsibilities:
- Accept a validated GenerateCVRequest (external API payload).
- Fetch hydrated data from eport_data_api (student, role, JD, etc.).
- Assemble the Stage-0 payload aligned with eport_generation.input_schema.
- Call the CV generation service and map its result into a clean
  GenerateCVResponse envelope.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import httpx
import structlog
from urllib.parse import quote

from functions.utils.settings import get_settings
from functions.orchestrator.data_fetcher import DataFetcher, load_orchestrator_config
from functions.orchestrator.profile_normalizer import normalize_student_profile_for_stage0
from functions.orchestrator.role_normalizer import normalize_role_taxonomy_for_stage0
from functions.orchestrator.job_normalizer import normalize_job_taxonomy_for_stage0
from schemas.input_schema import GenerateCVRequest
from schemas.output_schema import GenerateCVError, GenerateCVResponse, GeneratedCV
from schemas.stage0_schema import (
    JobTaxonomy,
    RoleTaxonomy,
    Stage0CVGenerationRequest,
    StudentProfile,
    Language,
    LanguageTone,
)

logger = structlog.get_logger(__name__)


# ------------------------------------------------------------
# URL Helper — Encode IDs containing "#"
# ------------------------------------------------------------
def _encode_id_for_path(raw_id: Optional[str]) -> Optional[str]:
    """
    Convert IDs like 'role#ai_engineer' → 'role%23ai_engineer'.

    Rules:
    - If raw_id is None → return None.
    - If raw_id already encoded (no '#'), return as-is.
    - Only encode '#' to avoid fragment stripping.
    """
    if raw_id is None:
        return None
    if "#" in raw_id:
        return quote(raw_id, safe="")
    return raw_id


class OrchestratorService:
    """
    Orchestrates data fetching and CV generation.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.data_fetcher = DataFetcher(self.settings)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def generate_cv(self, req: GenerateCVRequest) -> GenerateCVResponse:
        """
        Steps:
        1. Encode IDs for safe URL usage.
        2. Parallel fetch student profile, role taxonomy (optional),
           JD taxonomy (optional), and template info.
        3. Build Stage-0 payload.
        4. Call generation service.
        5. Map response.
        """

        # --------------------------------------------------------
        # 1) Encode problematic IDs BEFORE passing to DataFetcher
        # --------------------------------------------------------
        encoded_role_id = _encode_id_for_path(req.role_id)
        encoded_jd_id = _encode_id_for_path(req.jd_id)

        # 2) Parallel data fetching from eport_data_api
        try:
            student_task = asyncio.create_task(
                self.data_fetcher.fetch_student_profile(req.student_id)
            )

            role_task = asyncio.create_task(
                self.data_fetcher.fetch_role_taxonomy(encoded_role_id)
            )

            jd_task = asyncio.create_task(
                self.data_fetcher.fetch_jd_taxonomy(encoded_jd_id)
            )

            template_task = asyncio.create_task(
                self.data_fetcher.fetch_template_info(req.template_id)
            )

            (
                student_raw,
                role_raw,
                jd_raw,
                template_raw,
            ) = await asyncio.gather(
                student_task,
                role_task,
                jd_task,
                template_task,
            )

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "data_fetch_failed",
                student_id=req.student_id,
                role_id=encoded_role_id,
                jd_id=encoded_jd_id,
                template_id=req.template_id,
                error=str(exc),
            )
            error = GenerateCVError(
                code="ORCH_DATA_API_ERROR",
                message="Failed to fetch required data from eport_data_api.",
                details={"reason": str(exc)},
            )
            return GenerateCVResponse(
                status="error",
                cv=None,
                error=error,
                user_or_llm_comments=req.user_or_llm_comments,
                request_metadata=req.request_metadata,
            )

        # 3) Build Stage-0 payload
        try:
            stage0_payload = self._build_stage0_payload(
                req=req,
                student_raw=student_raw,
                role_raw=role_raw,
                jd_raw=jd_raw,
            )
        except Exception as exc:
            logger.error(
                "stage0_build_failed",
                student_id=req.student_id,
                error=str(exc),
            )
            error = GenerateCVError(
                code="ORCH_STAGE0_BUILD_ERROR",
                message="Failed to construct Stage-0 payload for generation.",
                details={"reason": str(exc)},
            )
            return GenerateCVResponse(
                status="error",
                cv=None,
                error=error,
                user_or_llm_comments=req.user_or_llm_comments,
                request_metadata=req.request_metadata,
            )

        # 4) Call CV generation service
        try:
            generation_result = await self._call_generation_service(stage0_payload)
        except httpx.HTTPError as exc:
            logger.error("generation_service_http_error", error=str(exc))
            error = GenerateCVError(
                code="ORCH_GENERATION_HTTP_ERROR",
                message="Failed to call CV generation service.",
                details={"reason": str(exc)},
            )
            return GenerateCVResponse(
                status="error",
                cv=None,
                error=error,
                user_or_llm_comments=req.user_or_llm_comments,
                request_metadata=req.request_metadata,
            )
        except Exception as exc:
            logger.error("generation_service_unexpected_error", error=str(exc))
            error = GenerateCVError(
                code="ORCH_GENERATION_ERROR",
                message="Unexpected error while generating CV.",
                details={"reason": str(exc)},
            )
            return GenerateCVResponse(
                status="error",
                cv=None,
                error=error,
                user_or_llm_comments=req.user_or_llm_comments,
                request_metadata=req.request_metadata,
            )

        # 5) Map generation result
        cv = self._map_generation_result_to_cv(generation_result, req)

        return GenerateCVResponse(
            status="success",
            cv=cv,
            error=None,
            user_or_llm_comments=req.user_or_llm_comments,
            request_metadata=req.request_metadata,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _build_stage0_payload(
        self,
        req: GenerateCVRequest,
        student_raw: Dict[str, Any],
        role_raw: Optional[Dict[str, Any]],
        jd_raw: Optional[Dict[str, Any]],
    ) -> Stage0CVGenerationRequest:
        # ---------------------------
        # Student profile
        # ---------------------------
        inner = student_raw.get("student_profile", student_raw)
        normalized_student = normalize_student_profile_for_stage0(inner)
        student_profile = StudentProfile.model_validate(normalized_student)

        # ---------------------------
        # Role taxonomy (optional)
        # ---------------------------
        role_taxonomy: Optional[RoleTaxonomy] = None
        if role_raw:
            normalized_role = normalize_role_taxonomy_for_stage0(role_raw)
            role_taxonomy = RoleTaxonomy.model_validate(normalized_role)

        # ---------------------------
        # Job taxonomy (optional)
        # ---------------------------
        job_taxonomy: Optional[JobTaxonomy] = None
        if jd_raw:
            normalized_jd = normalize_job_taxonomy_for_stage0(jd_raw)
            job_taxonomy = JobTaxonomy.model_validate(normalized_jd)

        jd_required_skills = (
            job_taxonomy.job_required_skills if job_taxonomy else None
        )

        user_input_sections = (
            dict(req.user_input_cv_text_by_section)
            if isinstance(req.user_input_cv_text_by_section, dict)
            else None
        )

        stage0 = Stage0CVGenerationRequest(
            user_id=req.student_id,
            language=req.language,
            language_tone=req.language_tone,
            template_id=req.template_id,
            sections=req.sections,
            student_profile=student_profile,
            user_input_cv_text_by_section=user_input_sections,
            target_role_taxonomy=role_taxonomy,
            target_jd_taxonomy=job_taxonomy,
            jd_required_skills=jd_required_skills,
        )

        logger.info(
            "stage0_payload_built",
            user_id=stage0.user_id,
            language=stage0.language.value,
            template_id=stage0.template_id,
            sections=stage0.sections,
        )

        return stage0


    async def _call_generation_service(
        self, stage0: Stage0CVGenerationRequest
    ) -> Dict[str, Any]:

        settings = self.settings
        config = load_orchestrator_config()

        path_template = config["generation_api"]["endpoints"]["generate_cv"]
        base = str(settings.generation_api_base_url).rstrip("/")
        url = base + path_template
        logger.info("calling_generation_service", url=url)

        async with httpx.AsyncClient(
            timeout=settings.generation_timeout_seconds
        ) as client:
            payload = stage0.model_dump(mode="json", exclude_none=True)

            # Remove comments if disabled by settings flag
            if not self.settings.enable_user_or_llm_comments:
                payload.pop("user_or_llm_comments", None)

            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        logger.info("generation_service_success", url=url)
        return data

    def _map_generation_result_to_cv(
        self,
        generation_result: Dict[str, Any],
        req: GenerateCVRequest,
    ) -> GeneratedCV:

        lang_value = generation_result.get("language")
        tone_value = generation_result.get("language_tone")

        try:
            language = Language(lang_value) if lang_value else req.language
        except ValueError:
            language = req.language

        try:
            language_tone = (
                LanguageTone(tone_value) if tone_value else req.language_tone
            )
        except ValueError:
            language_tone = req.language_tone

        cv = GeneratedCV(
            job_id=generation_result.get("job_id"),
            template_id=generation_result.get("template_id", req.template_id),
            language=language,
            language_tone=language_tone,
            rendered_html=generation_result.get("rendered_html"),
            rendered_markdown=generation_result.get("rendered_markdown"),
            sections=generation_result.get("sections"),
            raw_generation_result=generation_result,
        )

        logger.info(
            "generation_result_mapped",
            job_id=cv.job_id,
            template_id=cv.template_id,
        )

        return cv
