# functions/orchestrator/role_normalizer.py
from typing import Any, Dict, List

def normalize_role_taxonomy_for_stage0(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert role taxonomy response into the structure required by Stage-0.
    Specifically, convert role_required_skills into List[str] of skill names.
    """

    out = raw.copy()

    normalized_skills: List[str] = []
    for item in raw.get("role_required_skills", []):
        # API may return either dict or pure string
        if isinstance(item, str):
            normalized_skills.append(item)
        elif isinstance(item, dict):
            # Prefer skill_name / name / id fallback
            skill_name = (
                item.get("skill_name")
                or item.get("name")
                or item.get("skill_id")
                or "Unknown Skill"
            )
            normalized_skills.append(skill_name)

    out["role_required_skills"] = normalized_skills
    return out
