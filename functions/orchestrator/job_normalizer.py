from __future__ import annotations

from typing import Any, Dict, List


def normalize_job_taxonomy_for_stage0(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize job taxonomy payload from eport_data_api into the schema
    expected by Stage-0 JobTaxonomy.

    Notes:
    - Data API returns rich / denormalized structures (dicts per skill,
      responsibility, company metadata, etc.).
    - Stage-0 JobTaxonomy currently expects a minimal, strict schema
      (mostly list[str]).
    - This function intentionally:
        * Flattens lists of dicts -> list[str]
        * Drops extra fields to avoid `extra_forbidden`
        * Keeps mapping logic explicit and easy to adjust later

    If/when JobTaxonomy is expanded (e.g. structured skills with levels,
    company info, location), update this function accordingly.
    """

    # --------------------------------------------------
    # Required skills
    # --------------------------------------------------
    # Data API example:
    # {"jd_id": "...", "skill_id": "...", "proficiency_lv": "..."}
    # Stage-0 expects: list[str]
    required_skills: List[str] = []
    for item in raw.get("job_required_skills", []):
        if isinstance(item, str):
            required_skills.append(item)
        elif isinstance(item, dict):
            skill = (
                item.get("skill_id")
                or item.get("skill_code")
                or item.get("skill_name")
                or item.get("name")
            )
            if skill:
                required_skills.append(skill)

    # --------------------------------------------------
    # Responsibilities
    # --------------------------------------------------
    # Data API example:
    # {"jd_id": "...", "responsibility": "..."}
    # Stage-0 expects: list[str]
    responsibilities: List[str] = []
    for item in raw.get("job_responsibilities", []):
        if isinstance(item, str):
            responsibilities.append(item)
        elif isinstance(item, dict):
            text = item.get("responsibility")
            if text:
                responsibilities.append(text)

    return {
        # Use canonical Stage-0 field names only
        "job_id": raw.get("job_id") or raw.get("jd_id"),
        "job_title": raw.get("job_title") or raw.get("title"),
        "job_required_skills": required_skills,
        "job_responsibilities": responsibilities,
    }
