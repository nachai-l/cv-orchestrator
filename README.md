# E-Port Orchestrator API

The **E-Port Orchestrator API** is a **Backend-for-Frontend (BFF)** service responsible for orchestrating **end-to-end CV generation** across multiple internal services.

It provides a **single, stable, frontend-facing API** while encapsulating all data fetching, normalization, validation, and LLM orchestration logic.

---

## High-Level Purpose

This service exists to:

* Shield frontend clients from:
  * Multiple backend APIs
  * Complex schema contracts
  * Multi-stage LLM pipelines
* Enforce **strict input validation and safety guarantees**
* Produce **auditable, deterministic, schema-compliant CV outputs**
* Enable future evolution of data sources and generation logic **without breaking clients**

---

## Architecture Overview

The Orchestrator coordinates the following internal services:

### 1. E-Port Data API (`eport_data_api`)

Provides canonical data objects:

* Student profile
* Role taxonomy (optional)
* Job description (JD) taxonomy (optional)
* CV template metadata

✅ API implementation complete  
⚠️ Data is currently **mocked** (IDs are stable, values may change)

---

### 2. CV Generation Service (`cv_generation_service`)

Executes the **Stage A–D CV Generation Pipeline**, including:

* Guardrails & sanitization
* Gemini 2.5 Flash generation (hardened)
* Factuality & schema validation
* Evidence-based justification

---

### End-to-End Flow

```

Client
|
| POST /api/v1/cv-generations        (recommended)
| POST /v1/orchestrator/generate-cv  (deprecated alias)
v
E-Port Orchestrator API (BFF)
├─ Validate request + enums
├─ Fetch data from eport_data_api
├─ Normalize & assemble Stage-0 payload
├─ Call CV Generation Service (/generate_cv)
└─ Return stable response envelope

```

---

## Responsibilities (Detailed)

### 1. External Request Validation

* Accepts **only identifiers and generation options**
* Rejects:
  * Raw profile text
  * Arbitrary prompts
  * Invalid enum values
* Ensures predictable behavior and injection resistance

**Request naming policy**

* ✅ Preferred: **camelCase** at API boundary
* ✅ Backward compatible: **snake_case** is still accepted
* ✅ Internally normalized into typed Pydantic models

---

### 2. Data Hydration (from `eport_data_api`)

The orchestrator fetches required objects from **eport_data_api**
(**API complete; data currently mocked**):

* `student_full_profile` (required)
* `template_info` (required)
* `role_taxonomy` (optional)
* `jd_taxonomy` (optional)

If role or JD is provided:

* Their schemas are **strictly validated**
* Missing or empty required fields (e.g. role skills) result in **hard errors**

---

### 3. Stage-0 Payload Assembly

The orchestrator constructs a **validated Stage-0 payload** that is:

* Strictly aligned with `schemas.stage0_schema`
* Compatible with the CV Generation Service
* Free from user-injected instructions

This payload becomes the **single source of truth** for downstream generation.

---

### 4. CV Generation Invocation

* Calls `/generate_cv` on the CV Generation Service
* Applies:
  * Timeout control
  * Retry logic
  * Structured error propagation
* Does **not** expose internal generation stages to clients

---

### 5. Response Normalization

Returns a **stable response envelope** that includes:

* Final CV sections (frontend-ready)
* Structured metadata (timing, model, cost, validation)
* Raw Stage-D output (for audit/debug)
* User comments and request metadata (pass-through)

**Response naming policy**

* ✅ **camelCase enforced** at API boundary (success + error)

---

## API Specification

📄 **Authoritative API contract** is documented in:

```

api_spec/API_spec.md

```

The API spec includes:

* Full request & response schemas
* Optional vs required fields
* Supported enum values
* Browser-callable examples
* Error codes & failure scenarios
* Mocked IDs currently available
* Alignment with the CV Generation Service (Stage 0–D)

> **README = conceptual & operational overview**  
> **API_spec.md = contract you code against**

---

## Supported Generation Modes

The same endpoint supports multiple modes:

1. **Student-only CV**
   * No role, no JD
   * General-purpose professional CV

2. **Role-aware CV**
   * Role taxonomy provided
   * Skill framing adjusted to role expectations

3. **JD-aligned CV**
   * Specific JD taxonomy provided
   * Skill matching, alignment metrics enabled

Role and JD are **optional**, but **strictly validated if present**.

---

## Current Supported Enums

### Language

* `en`
* `th` (future-ready)

### Language Tone (current, subject to change)

* `formal`
* `neutral`
* `academic`
* `funny`
* `casual`

Enum validation is enforced at the orchestrator boundary.

---

## Project Structure

```

.
├── api.py                         # FastAPI app + public endpoints
├── api_spec/
│   └── API_spec.md                # Formal API contract
├── functions/
│   ├── orchestrator/
│   │   ├── eport_orchestrator_service.py   # Core orchestration logic
│   │   ├── data_fetcher.py                 # Data API integration
│   │   ├── profile_normalizer.py
│   │   ├── role_normalizer.py
│   │   └── job_normalizer.py
│   ├── utils/
│   │   ├── settings.py                     # ENV + parameters.yaml loading
│   │   ├── http_client.py                  # Shared HTTP utilities
│   │   └── json_naming_converter.py        # snake_case -> camelCase response converter
│   └── models/                             # Reserved for future use
├── schemas/
│   ├── input_schema.py             # External request schema (camelCase + snake_case accepted)
│   ├── output_schema.py            # External response envelope
│   └── stage0_schema.py            # Internal Stage-0 payload
├── parameters/
│   ├── parameters.yaml
│   └── config.yaml
├── tests/
│   ├── test_generate_cv_endpoint.py
│   ├── local_api_actual_tests.py   # Local smoke calls (optional / manual)
│   └── gcp_api_actual_tests.py     # GCP (Cloud Run) smoke calls (optional / manual)
├── Dockerfile
├── requirements.txt
└── README.md

````

---

## Configuration

Configuration precedence:

1. Environment variables
2. `parameters/parameters.yaml`
3. Safe defaults (non-critical only)

### Key Environment Variables

```bash
ENVIRONMENT=prod                 # local | dev | prod

DATA_API_BASE_URL=https://eport-data-api-xxxx.a.run.app
GENERATION_API_BASE_URL=https://cv-generation-service-xxxx.a.run.app

HTTP_TIMEOUT_SECONDS=30
GENERATION_TIMEOUT_SECONDS=300
MAX_RETRIES=2
LOG_LEVEL=INFO
````

---

## API Endpoints (Summary)

### Health Check

**GET `/health`** ✅ canonical (Cloud Run + local)
**GET `/healthz`** ⚠️ optional (may be 404 on Cloud Run)

Used for Cloud Run liveness and monitoring.

```json
{
  "status": "ok",
  "service": "eport_orchestrator_api",
  "environment": "prod"
}
```

---

### Create CV Generation (REST)

**POST `/api/v1/cv-generations`** ✅ recommended

Primary endpoint for all CV generation modes.

➡️ See **`api_spec/API_spec.md`** for full examples and constraints.

---

### Deprecated Alias (Backward Compatibility)

**POST `/v1/orchestrator/generate-cv`** (deprecated)

Same behavior as the REST endpoint but returns `200 OK` for legacy clients.

---

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run locally:

```bash
uvicorn api:app --reload --port 8002
```

Verify:

```bash
curl http://localhost:8002/health
```

---

## Testing

```bash
pytest -q
```

Current coverage includes:

* Health endpoint(s)
* Successful orchestration
* Request validation failures
* Error propagation + standardized error envelope
* Correlation ID + API version header behavior
* Deprecated alias behavior

### Manual / Actual API Smoke Tests (Not for CI)

These make **real HTTP calls** and are intended for manual runs only.

```bash
python tests/local_api_actual_tests.py
python tests/gcp_api_actual_tests.py
```

---

## Deployment (Cloud Run)

Build:

```bash
gcloud builds submit \
  --tag asia-southeast1-docker.pkg.dev/PROJECT_ID/cv-orchestrator/service:latest
```

Deploy:

```bash
gcloud run deploy cv-orchestrator \
  --image asia-southeast1-docker.pkg.dev/PROJECT_ID/cv-orchestrator/service:latest \
  --region asia-southeast1 \
  --platform managed \
  --service-account cv-orchestrator-sa@PROJECT_ID.iam.gserviceaccount.com
```

---

## Current Status

* ✅ Cloud Run deployed
* ✅ End-to-end smoke tested
* ✅ REST endpoint added: `POST /api/v1/cv-generations`
* ✅ Backward compatible alias supported: `POST /v1/orchestrator/generate-cv`
* ✅ Accepts camelCase + snake_case requests
* ✅ camelCase enforced for responses (success + error)
* ✅ Optional role/JD supported
* ✅ Stage-0 validation enforced
* ⚠️ Data API values mocked

```
```

