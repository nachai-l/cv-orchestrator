# functions/orchestrator/data_fetcher.py

"""
DataFetcher for the Orchestrator API.

Responsibilities:
- Call eport_data_api to fetch:
    * Student full profile
    * Role taxonomy
    * JD taxonomy
    * Template info
- Endpoint paths are read from parameters/config.yaml.
- Provide small, focused async helpers that return raw dicts.
- Handle basic retries and logging, leaving higher-level error handling
  to OrchestratorService.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import structlog
import yaml

from functions.utils.settings import Settings

logger = structlog.get_logger(__name__)

CONFIG_PATH = Path(__file__).resolve().parents[2] / "parameters" / "config.yaml"


@lru_cache(maxsize=1)
def load_orchestrator_config() -> Dict[str, Any]:
    """
    Load static orchestrator configuration from parameters/config.yaml.

    This is used primarily for endpoint paths so we don't hardcode them in code.
    """
    if not CONFIG_PATH.exists():
        logger.warning(
            "orchestrator_config_missing",
            path=str(CONFIG_PATH),
        )
        return {}

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    logger.info("orchestrator_config_loaded", path=str(CONFIG_PATH))
    return data


class DataFetcher:
    """
    Thin client around eport_data_api.

    It does not perform heavy validation; instead:
    - Exposes raw JSON dicts back to OrchestratorService.
    - Lets Pydantic models (Stage-0 schema) perform structural validation.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

        # Base URL for eport_data_api (AnyHttpUrl -> str)
        self._base_url = str(settings.data_api_base_url).rstrip("/")

        # Static endpoint path templates from parameters/config.yaml
        self._config = load_orchestrator_config()
        self._student_full_profile_path = self._config["data_api"]["endpoints"][
            "student_full_profile"
        ]
        self._role_taxonomy_path = self._config["data_api"]["endpoints"][
            "role_taxonomy"
        ]
        self._jd_taxonomy_path = self._config["data_api"]["endpoints"]["jd_taxonomy"]
        self._template_info_path = self._config["data_api"]["endpoints"][
            "template_info"
        ]

        # Retry & timeout settings
        self._timeout = settings.http_timeout_seconds
        self._max_retries = settings.max_retries

    # ------------------------------------------------------------------ #
    # Public async methods
    # ------------------------------------------------------------------ #
    async def fetch_student_profile(self, student_id: str) -> Dict[str, Any]:
        """
        Fetch the full hydrated student profile.

        Path template from config.yaml:
            data_api.endpoints.student_full_profile
        """
        template = self._get_endpoint_template(
            section="data_api",
            key="student_full_profile",
        )
        path = template.format(student_id=student_id)
        return await self._get_json(path, context={"student_id": student_id})

    async def fetch_role_taxonomy(
        self, role_id: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch role taxonomy by role_id (if provided).

        Path template from config.yaml:
            data_api.endpoints.role_taxonomy

        If role_id is None, returns None without calling the API.
        """
        if not role_id:
            return None

        template = self._get_endpoint_template(
            section="data_api",
            key="role_taxonomy",
        )
        path = template.format(role_id=role_id)
        return await self._get_json(path, context={"role_id": role_id})

    async def fetch_jd_taxonomy(
        self, jd_id: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch job/JD taxonomy by jd_id (if provided).

        Path template from config.yaml:
            data_api.endpoints.jd_taxonomy

        If jd_id is None, returns None without calling the API.
        """
        if not jd_id:
            return None

        template = self._get_endpoint_template(
            section="data_api",
            key="jd_taxonomy",
        )
        path = template.format(jd_id=jd_id)
        return await self._get_json(path, context={"jd_id": jd_id})

    async def fetch_template_info(self, template_id: str) -> Dict[str, Any]:
        """
        Fetch template info by template_id.

        Path template from config.yaml:
            data_api.endpoints.template_info
        """
        template = self._get_endpoint_template(
            section="data_api",
            key="template_info",
        )
        path = template.format(template_id=template_id)
        return await self._get_json(path, context={"template_id": template_id})

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _get_endpoint_template(self, section: str, key: str) -> str:
        """
        Read an endpoint path template from the loaded config.

        Example:
            section="data_api", key="student_full_profile"
            → "/v1/students/{student_id}/full-profile"
        """
        try:
            template = self._config[section]["endpoints"][key]
            if not isinstance(template, str):
                raise TypeError("Endpoint template is not a string")
            return template
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "endpoint_template_missing_or_invalid",
                section=section,
                key=key,
                error=str(exc),
            )
            # Fail fast; this is a deployment/config error, not a runtime glitch
            raise RuntimeError(
                f"Missing or invalid endpoint template for {section}.{key}"
            ) from exc

    async def _get_json(
        self,
        path: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Perform a GET request to eport_data_api and return JSON.

        - Applies a simple retry loop using configured max_retries.
        - Raises httpx.HTTPError if all attempts fail.
        """
        url = self._base_url + path
        ctx = context or {}

        last_exc: Exception | None = None

        for attempt in range(1, self._max_retries + 2):  # e.g. max_retries=2 => 3 attempts
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    data = resp.json()

                logger.info(
                    "data_fetch_success",
                    url=url,
                    attempt=attempt,
                    **ctx,
                )
                return data

            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning(
                    "data_fetch_attempt_failed",
                    url=url,
                    attempt=attempt,
                    max_retries=self._max_retries,
                    error=str(exc),
                    **ctx,
                )
                # If this was the last allowed attempt, re-raise
                if attempt >= self._max_retries + 1:
                    logger.error(
                        "data_fetch_exhausted_retries",
                        url=url,
                        attempts=attempt,
                        error=str(exc),
                        **ctx,
                    )
                    raise

        # Should never reach here, but keeps mypy happy
        assert last_exc is not None
        raise last_exc
