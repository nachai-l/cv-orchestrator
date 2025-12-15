# functions/utils/settings.py

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import structlog
import yaml
from pydantic import AnyHttpUrl, ValidationError, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = structlog.get_logger(__name__)

PARAMETERS_PATH = Path(__file__).resolve().parents[2] / "parameters" / "parameters.yaml"


class Settings(BaseSettings):
    """
    Runtime settings for the Orchestrator API.

    Load order / precedence:
        1. YAML defaults (parameters/parameters.yaml)
        2. Environment variables (EPORT_ORCH_*), overriding YAML
    """

    model_config = SettingsConfigDict(
        env_prefix="EPORT_ORCH_",
        extra="ignore",
    )

    # Service metadata
    service_name: str = "eport_orchestrator_api"
    environment: str = "local"
    log_level: str = "INFO"

    # Sister service URLs
    # These are logically required, but kept Optional in the raw model so we can
    # merge YAML + env first, then enforce presence explicitly in get_settings().
    data_api_base_url: Optional[AnyHttpUrl] = None
    generation_api_base_url: Optional[AnyHttpUrl] = None

    # Internal networking timeouts
    http_timeout_seconds: float = 15.0
    generation_timeout_seconds: float = 60.0
    max_retries: int = 2

    # Request tracing
    request_id_header: str = "X-Request-ID"

    # Feature flags
    enable_user_or_llm_comments: bool = Field(
        default=False,
        description=(
            "If true, orchestrator will include user_or_llm_comments "
            "in the Stage-0 payload to eport_generation (once supported)."
        ),
    )


@lru_cache(maxsize=1)
def _load_yaml_parameters() -> Dict[str, Any]:
    """Load base configuration from parameters/parameters.yaml (if present)."""
    if not PARAMETERS_PATH.exists():
        logger.warning("parameters_yaml_missing", expected=str(PARAMETERS_PATH))
        return {}

    try:
        with PARAMETERS_PATH.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            logger.warning(
                "parameters_yaml_not_dict",
                path=str(PARAMETERS_PATH),
                type=type(data).__name__,
            )
            return {}
        logger.info("parameters_yaml_loaded", path=str(PARAMETERS_PATH))
        return data
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "parameters_yaml_load_error",
            path=str(PARAMETERS_PATH),
            error=str(exc),
        )
        return {}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Load settings by merging YAML + env, then enforce required URLs.

    Steps:
        1. Load YAML defaults (if any).
        2. Load env-based Settings() (fields may be None / unset).
        3. Merge: YAML as base, env overrides on top.
        4. Enforce that data_api_base_url and generation_api_base_url are set.
        5. Validate the merged dict via Settings.model_validate().
    """

    # -------------------------
    # 1) Load YAML defaults
    # -------------------------
    yaml_data = _load_yaml_parameters()

    # -------------------------
    # 2) Load env-based override (partial)
    # -------------------------
    try:
        env_settings = Settings()
        env_data = env_settings.model_dump(exclude_unset=True)
        logger.info(
            "settings_loaded_env_only_partial",
            fields=list(env_data.keys()),
        )
    except ValidationError as exc:
        logger.warning(
            "settings_env_validation_error",
            errors=exc.errors(),
        )
        env_data = {}

    # -------------------------
    # 3) Merge dicts
    # YAML as base → env overrides
    # -------------------------
    merged: Dict[str, Any] = {**yaml_data, **env_data}

    # -------------------------
    # 4) Required fields check
    # -------------------------
    missing: list[str] = []
    if not merged.get("data_api_base_url"):
        missing.append("data_api_base_url")
    if not merged.get("generation_api_base_url"):
        missing.append("generation_api_base_url")

    if missing:
        logger.error(
            "settings_missing_required_urls",
            missing=missing,
            yaml_path=str(PARAMETERS_PATH),
        )
        raise RuntimeError(
            f"Missing required settings: {', '.join(missing)}. "
            "Set them either in environment variables (EPORT_ORCH_*) "
            f"or in {PARAMETERS_PATH}."
        )

    # -------------------------
    # 5) Final validation
    # Apply Settings model on the merged dict
    #
    # This correctly validates:
    # - URLs
    # - feature flags (e.g., enable_user_or_llm_comments)
    # -------------------------
    settings = Settings.model_validate(merged)

    logger.info(
        "settings_loaded",
        environment=settings.environment,
        service_name=settings.service_name,
        data_api_base_url=str(settings.data_api_base_url),
        generation_api_base_url=str(settings.generation_api_base_url),
        enable_user_or_llm_comments=settings.enable_user_or_llm_comments,
    )

    return settings
