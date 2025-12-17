# E-Port Orchestrator API — REST API Specification

Service: **eport_orchestrator_api (BFF)**
Purpose: Create CV generation results by orchestrating **eport_data_api** + **cv_generation_service**.

---

## Base URLs

**Production (Cloud Run):**
[https://cv-orchestrator-810737581373.asia-southeast1.run.app](https://cv-orchestrator-810737581373.asia-southeast1.run.app)

**Local:**
[http://127.0.0.1:8002](http://127.0.0.1:8002)

**Swagger / OpenAPI (prod):**
[https://cv-orchestrator-810737581373.asia-southeast1.run.app/docs](https://cv-orchestrator-810737581373.asia-southeast1.run.app/docs)

---

## Guideline Alignment Notes

* ✅ **Resource-based URL:** uses nouns and plural resources (`/api/v1/cv-generations`)
* ✅ **HTTP methods:** `POST` used for **resource creation** (generation job)
* ✅ **HTTP status codes:** `201 Created` for successful creation
* ✅ **Error format:** standard error schema `{code,message,subErrors,timestamp,correlationId}`
* ✅ **Correlation ID:** `X-Correlation-Id` supported (passthrough + server-generated)
* ✅ **API Version header:** `X-API-Version` supported + validated (currently supports `1`)
* ✅ **Naming convention:** URL is lowercase + kebab-case
* ✅ **JSON naming (response):** **camelCase enforced at API boundary**
* ✅ **JSON naming (request):** **accepts both camelCase + snake_case** (backward compatible)

> Note: Response camelCase is enforced via a converter at the API boundary. Error responses use camelCase keys as well.

---

## Authentication & Authorization

**[In Progress — not enforced yet]** Guideline supports:

### External Gateway (Bearer JWT)

Authorization: Bearer

### Internal Network (X-API-Key)

X-API-Key:

### Gateway → Internal Header Mapping (recommended)

**[In Progress — not implemented]**
X-User-Id: <jwt.sub>
X-User-Name: <jwt.name>
X-User-Email: <jwt.email>
X-User-Roles: <jwt.roles>

---

## Required Headers

### Content Type

Content-Type: application/json

### Correlation ID

* Client **may provide** `X-Correlation-Id`
* If missing, server generates: `corr_<uuidhex>`
* Server always echoes `X-Correlation-Id` in responses (success + error)

Example:
X-Correlation-Id: abc123def456

### API Version

Header versioning supported (URL versioning remains primary via `/api/v1/...`).

✅ Implemented: `X-API-Version` (currently only `1` supported)

Example:
X-API-Version: 1

If invalid → `400 INVALID_FIELD_VALUE`.

**Response behavior:** server **echoes** `X-API-Version` on all responses (success + error).

---

## Endpoints Summary

### Health
* `GET /health` ✅ canonical (works on Cloud Run + local)
* `GET /healthz` ⚠️ local-only / not guaranteed in Cloud Run

### CV Generation (REST)

* `POST /api/v1/cv-generations` ✅ recommended

### CV Generation (Deprecated Alias)

* `POST /v1/orchestrator/generate-cv` ✅ supported for backward compatibility
  (verb-like URL; keep until clients migrate)

---

## 1) Health Endpoints

### GET /health ✅ canonical
**Response:** `200 OK`

```json
{
  "status": "ok",
  "service": "eport_orchestrator_api",
  "environment": "prod"
}
```

### GET /healthz ⚠️ optional

Healthz is not guaranteed to be exposed in all deployments.
* Local dev may expose /healthz
* Cloud Run deployment may return 404 Not Found


---

## 2) Create CV Generation (REST)

### POST /api/v1/cv-generations

Creates a CV generation resource by:

* validating request
* fetching canonical objects from eport_data_api
* assembling Stage-0 payload
* calling cv_generation_service
* returning a stable response envelope

### Status Codes

* `201 Created` — success
* `400 Bad Request` — validation failed / invalid API version
* `401 Unauthorized` — **[In Progress - not enforced]**
* `404 Not Found` — upstream resource missing (student_id, template_id, role_id, jd_id)
* `500 Internal Server Error` — unexpected failure

---

## Request Schema

✅ **Input supports BOTH camelCase and snake_case keys** (clients may send either).

### Example (snake_case)

```json
{
  "student_id": "U-1001",
  "role_id": "role#ai_engineer",
  "jd_id": "jd#ai_lead_gov_2025",
  "template_id": "T_EMPLOYER_STD_V3",
  "language": "th",
  "language_tone": "formal",
  "sections": ["profile_summary", "skills", "experience", "education"],
  "user_or_llm_comments": {
    "profile_summary": "Emphasize leadership and government projects"
  },
  "request_metadata": {
    "source": "cloud-run"
  }
}
```

### Example (camelCase)

```json
{
  "studentId": "U-1001",
  "roleId": "role#ai_engineer",
  "jdId": "jd#ai_lead_gov_2025",
  "templateId": "T_EMPLOYER_STD_V3",
  "language": "th",
  "languageTone": "formal",
  "sections": ["profile_summary", "skills", "experience", "education"],
  "userOrLlmComments": {
    "profile_summary": "Emphasize leadership and government projects"
  },
  "requestMetadata": {
    "source": "cloud-run"
  }
}
```

### Field Definitions

| Field                                    | Type          | Required | Notes                                               |
| ---------------------------------------- | ------------- | -------: | --------------------------------------------------- |
| student_id / studentId                   | string        |        ✅ | ID of student profile                               |
| role_id / roleId                         | string        |        ❌ | Optional role taxonomy                              |
| jd_id / jdId                             | string        |        ❌ | Optional job description taxonomy                   |
| template_id / templateId                 | string        |        ✅ | CV template to structure output                     |
| language                                 | enum          |        ✅ | en, th                                              |
| language_tone / languageTone             | enum          |        ✅ | formal, neutral, academic, funny, casual            |
| sections                                 | array[string] |        ✅ | e.g. profile_summary, skills, experience, education |
| user_or_llm_comments / userOrLlmComments | object        |        ❌ | Hints per section (sanitized/guardrailed)           |
| request_metadata / requestMetadata       | object        |        ❌ | Pass-through metadata (source, tags, etc.)          |

---

## Successful Response

**201 Created**

Headers:

* X-Correlation-Id: corr_...
* X-API-Version: 1

Body (**camelCase enforced**):

```json
{
  "status": "success",
  "cv": {
    "jobId": "JOB_U-1001",
    "templateId": "T_EMPLOYER_STD_V3",
    "language": "th",
    "languageTone": "formal",
    "renderedHtml": null,
    "renderedMarkdown": null,
    "sections": {
      "profile_summary": {
        "text": "....",
        "wordCount": 17,
        "matchedJdSkills": [],
        "confidenceScore": 1.0
      },
      "skills": {
        "text": "- ...",
        "wordCount": 15,
        "matchedJdSkills": [],
        "confidenceScore": 1.0
      }
    },
    "rawGenerationResult": {
      "status": "completed",
      "metadata": {
        "generatedAt": "2025-12-16T15:55:22.304954Z",
        "modelVersion": "gemini-2.5-flash",
        "tokensUsed": 11124,
        "costEstimateThb": 0.2899,
        "requestId": "REQ_1765900522308"
      }
    }
  },
  "error": null,
  "userOrLlmComments": {
    "profile_summary": "Emphasize leadership and government projects"
  },
  "requestMetadata": {
    "source": "cloud-run"
  }
}
```

### Notes

* `rawGenerationResult` is included for audit/debug traceability.
* The `status` field in body is retained for backward compatibility (HTTP status code is the primary success indicator).

---

## Curl Example (Prod)

```bash
curl -s -X POST \
  "https://cv-orchestrator-810737581373.asia-southeast1.run.app/api/v1/cv-generations" \
  -H "Content-Type: application/json" \
  -H "X-API-Version: 1" \
  -d '{
    "studentId": "U-1001",
    "roleId": "role#ai_engineer",
    "jdId": "jd#ai_lead_gov_2025",
    "templateId": "T_EMPLOYER_STD_V3",
    "language": "th",
    "languageTone": "formal",
    "sections": ["profile_summary", "skills", "experience", "education"],
    "userOrLlmComments": {
      "profile_summary": "Emphasize leadership and government projects"
    },
    "requestMetadata": {
      "source": "cloud-run"
    }
  }' | jq .
```

---

## 3) Deprecated Alias Endpoint

### POST /v1/orchestrator/generate-cv (Deprecated)

Behavior:

* Same request schema as REST endpoint (**accepts camelCase + snake_case**)
* Same response structure as REST endpoint (**camelCase enforced**)
* Returns `200 OK` (legacy behavior)

Migration guidance: use `POST /api/v1/cv-generations` for new clients.

---

## 4) Standard Error Format

All errors follow this schema (**camelCase keys**):

```json
{
  "code": "VALIDATION_FAILED",
  "message": "Validation failed",
  "subErrors": [
    {
      "field": "student_id",
      "errors": [
        {
          "code": "missing",
          "message": "Field required"
        }
      ]
    }
  ],
  "timestamp": 1750672014,
  "correlationId": "corr_abc123def456"
}
```

Response headers include (always):

* X-Correlation-Id: corr_...
* X-API-Version: 1

---

### 4.1 Validation Errors

**400 Bad Request — VALIDATION_FAILED**

Example (missing required fields):

```bash
curl -s -X POST \
  "http://127.0.0.1:8002/api/v1/cv-generations" \
  -H "Content-Type: application/json" \
  -H "X-API-Version: 1" \
  -d '{"language":"en"}' | jq .
```

---

### 4.2 Invalid API Version

**400 Bad Request — INVALID_FIELD_VALUE**

If X-API-Version is not supported (e.g. 2):

```json
{
  "code": "INVALID_FIELD_VALUE",
  "message": "Invalid API version",
  "subErrors": [
    {
      "field": "X-API-Version",
      "errors": [
        {
          "code": "isIn",
          "message": "Supported versions: 1"
        }
      ]
    }
  ],
  "timestamp": 1750672014,
  "correlationId": "corr_..."
}
```

---

### 4.3 Internal Server Error

**500 Internal Server Error — INTERNAL_SERVER_ERROR**

```json
{
  "code": "INTERNAL_SERVER_ERROR",
  "message": "Unexpected error while processing request.",
  "subErrors": [],
  "timestamp": 1750672014,
  "correlationId": "corr_..."
}
```

---

## 5) Enumerations

### language

* en
* th

### language_tone (current; may evolve)

* formal
* neutral
* academic
* funny
* casual

---

## 6) Pagination & Filtering

Not applicable for POST /cv-generations.

**[Future]** If listing resources is added:

* GET /api/v1/cv-generations?page=1&limit=20 (max limit 100)

---

## 7) Internal Dependencies

### eport_data_api

Provides canonical objects:

* student profile (required)
* template info (required)
* role taxonomy (optional)
* JD taxonomy (optional)

✅ API implementation complete
⚠️ Data is currently mocked (IDs stable; values may change)

### cv_generation_service

Runs Stage A–D pipeline:

* guardrails & sanitization
* LLM generation (Gemini 2.5 Flash)
* factuality + schema validation
* evidence map / quality metrics

---

## 8) Change Log

* 2025-12-17: Added REST endpoint POST /api/v1/cv-generations (201 Created)
* 2025-12-17: Added X-Correlation-Id middleware (passthrough + generation)
* 2025-12-17: Added standard guideline error schema
* 2025-12-17: Added X-API-Version support (only version 1)
* 2025-12-17: Marked /v1/orchestrator/generate-cv as deprecated alias
* 2025-12-17: Enforced camelCase JSON for responses at API boundary via converter
* 2025-12-18: Updated request schema to accept **camelCase + snake_case** input keys (backward compatible)
* 2025-12-18: Standardized health checks to use `GET /health` as canonical (Cloud Run returns 404 for `/healthz`)
---
