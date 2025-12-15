# functions/orchestrator/profile_normalizer.py

from __future__ import annotations
from typing import Any, Dict, List, Optional

from dateutil import parser


def _fix_date(d: Optional[str]) -> Optional[str]:
    if not d:
        return None
    try:
        return parser.parse(d, dayfirst=True).date().isoformat()
    except Exception:
        return None


def _ensure_list(v: Any) -> List[Any]:
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        import json
        try:
            return json.loads(v)
        except Exception:
            return [x.strip() for x in v.split(",") if x.strip()]
    return []


def normalize_student_profile_for_stage0(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize eport_data_api full-profile into the Stage-0 StudentProfile shape.

    Maps source fields to Stage-0 names, normalizes dates, fixes list fields,
    and auto-fills missing IDs for now (freeform IDs until conventions are final).
    """

    # -----------------------------------------
    # Education
    # -----------------------------------------
    education = []
    for idx, ed in enumerate(raw.get("education", [])):
        start = _fix_date(ed.get("start_date"))
        grad = _fix_date(ed.get("graduation_date"))

        # Stage-0 requires graduation_date; fallback to start_date if missing
        if grad is None:
            grad = start

        education.append(
            {
                # Freeform ID for now. When the ID format is finalized, replace with:
                #   "id": ed.get("id") or f"edu#{idx+1}"
                "id": ed.get("id", f"edu-{idx+1}"),
                # Stage-0 expects `institution`, not `school_name`
                "institution": ed.get("institution") or ed.get("school_name"),
                "degree": ed.get("degree") or ed.get("education_level"),
                "major": ed.get("major"),
                "start_date": start,
                "graduation_date": grad,
                "gpa": ed.get("gpa"),
                "honors": ed.get("honors"),
            }
        )

    # -----------------------------------------
    # Experience
    # -----------------------------------------
    experience = []
    for idx, ex in enumerate(raw.get("experience", [])):
        resp_list = _ensure_list(ex.get("responsibilities"))

        experience.append(
            {
                # Freeform ID for now; later you can enforce `work_exp#...` etc.
                #   "id": ex.get("id") or f"work_exp#{idx+1}"
                "id": ex.get("id", f"exp-{idx+1}"),
                "company": ex.get("company"),
                "title": ex.get("title"),
                "start_date": _fix_date(ex.get("start_date")),
                "end_date": _fix_date(ex.get("end_date")),
                "responsibilities": resp_list,
            }
        )

    # -----------------------------------------
    # Skills
    # -----------------------------------------
    skills = []
    for idx, sk in enumerate(raw.get("skills", [])):
        name = sk.get("skill_name") or sk.get("name") or "Unnamed Skill"

        # Ensure description is at least 1 character
        desc = sk.get("description")
        if not desc or not isinstance(desc, str) or desc.strip() == "":
            desc = name  # fallback to skill name

        skills.append(
            {
                # Freeform ID for now; later enforce skill# pattern
                "id": sk.get("id", f"skill-{idx+1}"),
                "name": name,
                "description": desc,
                "level": sk.get("skill_level") or sk.get("level"),
            }
        )


    # -----------------------------------------
    # Awards
    # -----------------------------------------
    awards = []
    for idx, aw in enumerate(raw.get("awards", [])):
        date_iso = _fix_date(aw.get("date"))
        # Stage-0 requires a valid date; skip awards without one
        if not date_iso:
            continue

        awards.append(
            {
                # Freeform ID for now; later:
                #   "id": aw.get("id") or f"award#{idx+1}"
                "id": aw.get("id", f"award-{idx+1}"),
                # Stage-0 uses `title` and `issuer`
                "title": aw.get("title") or aw.get("name"),
                "issuer": aw.get("issuer") or aw.get("organization"),
                "date": date_iso,
            }
        )

    # -----------------------------------------
    # Extracurriculars
    # -----------------------------------------
    extracurriculars = []
    for idx, ex in enumerate(raw.get("extracurriculars", [])):
        extracurriculars.append(
            {
                # Freeform ID; later:
                #   "id": ex.get("id") or f"extra#{idx+1}"
                "id": ex.get("id", f"ext-{idx+1}"),
                # Stage-0 expects `title`, `organization`, `duration`
                "title": ex.get("title") or ex.get("name"),
                "organization": ex.get("organization"),
                "duration": ex.get("duration"),
                "description": ex.get("description"),
            }
        )

    # -----------------------------------------
    # Publications
    # -----------------------------------------
    pubs = []
    for idx, pub in enumerate(raw.get("publications", [])):
        pubs.append(
            {
                # Freeform ID; later:
                #   "id": pub.get("id") or f"pub#{idx+1}"
                "id": pub.get("id", f"pub-{idx+1}"),
                "title": pub.get("title"),
                "description": pub.get("description"),
            }
        )

    # -----------------------------------------
    # Training
    # -----------------------------------------
    training = []
    for idx, tr in enumerate(raw.get("training", [])):
        training.append(
            {
                # Freeform ID; later:
                #   "id": tr.get("id") or f"training#{idx+1}"
                "id": tr.get("id", f"train-{idx+1}"),
                # Stage-0 expects `title`
                "title": tr.get("title") or tr.get("name"),
                "description": tr.get("description"),
                "training_date": _fix_date(tr.get("training_date")),
            }
        )

    # -----------------------------------------
    # References
    # -----------------------------------------
    refs = []
    for idx, rf in enumerate(raw.get("references", [])):
        refs.append(
            {
                # Freeform ID; later:
                #   "id": rf.get("id") or f"ref#{idx+1}"
                "id": rf.get("id", f"ref-{idx+1}"),
                "name": rf.get("name"),
                "relationship": rf.get("relationship"),
            }
        )

    # -----------------------------------------
    # Additional Info
    # -----------------------------------------
    additional = []
    for idx, ad in enumerate(raw.get("additional_info", [])):
        additional.append(
            {
                # Freeform ID; later:
                #   "id": ad.get("id") or f"add#{idx+1}"
                "id": ad.get("id", f"add-{idx+1}"),
                "label": ad.get("label"),
                "value": ad.get("value"),
            }
        )

    return {
        "personal_info": raw.get("personal_info", {}),
        "education": education,
        "experience": experience,
        "skills": skills,
        "awards": awards,
        "extracurriculars": extracurriculars,
        "publications": pubs,
        "training": training,
        "references": refs,
        "additional_info": additional,
    }
