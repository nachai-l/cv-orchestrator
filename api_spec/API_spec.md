# CV Orchestrator API — Specification

## Overview

The **CV Orchestrator API** is a **Backend-for-Frontend (BFF)** service responsible for orchestrating data retrieval and CV generation across internal microservices.

It exposes **one external endpoint** that:

1. Accepts a lightweight request (IDs + options)
2. Fetches and hydrates required data from `eport_data_api` (**API complete; data currently mocked**)
3. Assembles a validated **Stage-0 payload**
4. Calls the **CV Generation Service** to execute the Stage A–D pipeline
5. Returns a clean, frontend-ready response

---

## Architecture Role

```
Client / UI
   |
   |  POST /v1/orchestrator/generate-cv
   v
CV Orchestrator API (BFF)
   ├─ fetch student_profile        (eport_data_api)
   ├─ fetch role_taxonomy (opt)     (eport_data_api)
   ├─ fetch jd_taxonomy (opt)       (eport_data_api)
   ├─ fetch template_info           (eport_data_api)
   ├─ build Stage-0 payload
   └─ POST /generate_cv             (cv-generation-service)
```

---

## Base URL (Production)

```
https://cv-orchestrator-<hash>.asia-southeast1.run.app
```

---

## Available Mocked IDs (Current)

### Students

* `U-1001`
* `U-1002`
* `U-1003`

### Roles

* `role#biotech_rnd_scientist`
* `role#ai_engineer`

### Job Descriptions

* `jd#mitsui_biotech_mgr_2025`
* `jd#ai_lead_gov_2025`

> ⚠️ Note: Missing or empty role/JD skill sets will result in a **Stage-0 validation error**.

---

## Endpoints

### 1. Health Check

#### `GET /health`

Simple liveness endpoint (browser-callable).

**Response**

```json
{
  "status": "ok",
  "service": "eport_orchestrator_api",
  "environment": "prod"
}
```

---

### 2. Generate CV

#### `POST /v1/orchestrator/generate-cv`

High-level CV generation entry point.

---

## Request Schema

### Required Fields

| Field           | Type          | Description             |
| --------------- | ------------- | ----------------------- |
| `student_id`    | string        | Platform user ID        |
| `template_id`   | string        | CV template identifier  |
| `language`      | enum          | Output language         |
| `language_tone` | enum          | Writing style           |
| `sections`      | array[string] | CV sections to generate |

---

### Optional Fields

| Field                           | Type   | Description                |
| ------------------------------- | ------ | -------------------------- |
| `role_id`                       | string | Role taxonomy ID           |
| `jd_id`                         | string | Job description ID         |
| `user_input_cv_text_by_section` | object | User-provided drafts       |
| `user_or_llm_comments`          | object | Free-form comments         |
| `request_metadata`              | object | Correlation / channel info |

---

### Enumerations

#### `language`

* `en`
* `th`

#### `language_tone` (current, subject to future change)

* `formal`
* `neutral`
* `academic`
* `funny`
* `casual`

#### `sections`

Allowed values:

```
profile_summary
skills
experience
education
projects
certifications
awards
extracurricular
volunteering
interests
publications
training
references
additional_info
```

---

## Example Requests

### A. Minimal (No Role / No JD)

```bash
curl -X POST https://cv-orchestrator-<hash>.run.app/v1/orchestrator/generate-cv \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "U-1002",
    "template_id": "T_EMPLOYER_STD_V3",
    "language": "en",
    "language_tone": "formal",
    "sections": ["profile_summary", "skills", "experience", "education"]
  }'
```

Behavior:

* Role inference disabled
* JD alignment treated as neutral
* Uses student profile only

---

### B. With Role and JD

```bash
curl -X POST https://cv-orchestrator-<hash>.run.app/v1/orchestrator/generate-cv \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "U-1002",
    "role_id": "role#ai_engineer",
    "jd_id": "jd#ai_lead_gov_2025",
    "template_id": "T_EMPLOYER_STD_V3",
    "language": "en",
    "language_tone": "formal",
    "sections": ["profile_summary", "skills", "experience", "education"],
    "user_or_llm_comments": {
      "profile_summary": "Emphasize leadership and government projects"
    },
    "request_metadata": {
      "source": "cloud-run"
    }
  }'
```

---

## Response Schema

### Success Response

```json
{
  "status": "success",
  "cv": {
    "job_id": "JOB_U-1002",
    "template_id": "T_EMPLOYER_STD_V3",
    "language": "en",
    "language_tone": "formal",
    "rendered_html": null,
    "rendered_markdown": null,
    "sections": {
      "profile_summary": {
        "text": "...",
        "word_count": 96,
        "matched_jd_skills": [],
        "confidence_score": 1.0
      }
    },
    "raw_generation_result": { "... full Stage-D payload ..." }
  },
  "error": null,
  "user_or_llm_comments": { ... },
  "request_metadata": { ... }
}
```

---

### Error Response

```json
{
  "status": "error",
  "cv": null,
  "error": {
    "code": "ORCH_STAGE0_BUILD_ERROR",
    "message": "Failed to construct Stage-0 payload",
    "details": {
      "reason": "role_required_skills must contain at least 1 item"
    }
  }
}
```

---

## Validation Rules (Orchestrator Level)

| Rule               | Behavior          |
| ------------------ | ----------------- |
| Missing student    | Error             |
| Empty role skills  | Error             |
| Empty JD skills    | Allowed           |
| Invalid enum       | 400               |
| Duplicate sections | Auto-deduplicated |
| Unknown fields     | Rejected          |

---

## Stage-0 Composition (Internal)

The orchestrator constructs the **Stage-0 Expected Input Payload** for the CV Generation Service:

| Component                       | Required |
| ------------------------------- | -------- |
| `student_profile`               | ✅        |
| `template_info`                 | ✅        |
| `cv_language`                   | ✅        |
| `job_role_info`                 | Optional |
| `job_position_info`             | Optional |
| `user_input_cv_text_by_section` | Optional |

This payload is then sent to:

```
POST cv-generation-service /generate_cv
```

---

## Security & Access

* Public access enabled (for demo)
* Designed for **IAM / ID-token protection**
* No PII logged
* Prompt injection handled downstream (Stage A)

---

## Non-Goals (Out of Scope)

* PDF / HTML rendering
* Authentication UI
* Direct LLM access
* Long-term persistence

---

## Status

| Component             | Status         |
| --------------------- | -------------- |
| Orchestrator API      | ✅ Deployed     |
| CV Generation Service | ✅ Deployed     |
| Data API              | ✅ API complete |
| Data                  | ⚠️ Mocked      |
| Auth                  | 🔜 Planned     |

---

