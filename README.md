# E-port Orchestrator API

Backend-for-Frontend (BFF) service that orchestrates:

- **E-port Data API** (`eport_data_api`) – student profile + taxonomy hydration
- **E-port Generation Service** (`eport_generation`) – Stage A–D CV generation

It exposes a single external endpoint:

```http
POST /v1/orchestrator/generate-cv
````

---

## 1. Responsibilities

* Validate external requests (IDs + options, not full profile).
* Fetch hydrated data from `eport_data_api`:

  * `student_full_profile`
  * `role_taxonomy`
  * `jd_taxonomy`
  * `template_info`
* Assemble **Stage-0 payload** aligned with `eport_generation.input_schema`.
* Call `eport_generation` and return a clean **GenerateCVResponse** envelope.

---

## 2. Project Structure

```text
.
├── api.py                         # FastAPI app + endpoints
├── functions/
│   ├── orchestrator/
│   │   ├── eport_orchestrator_service.py  # Core orchestration logic
│   │   └── data_fetcher.py               # Calls eport_data_api
│   ├── utils/
│   │   ├── settings.py                   # ENV + parameters.yaml config
│   │   └── http_client.py                # Reserved for future shared HTTP logic
│   └── models/                           # Reserved for future internal models
├── schemas/
│   ├── input_schema.py           # External /v1/orchestrator/generate-cv request
│   ├── output_schema.py          # External response envelope
│   └── stage0_schema.py          # Internal Stage-0 payload (→ eport_generation)
├── parameters/
│   └── parameters.yaml           # Local/dev config fallback
├── tests/
│   └── test_generate_cv_endpoint.py
├── requirements.txt
└── Dockerfile
```

---

## 3. Configuration

Configuration is loaded in this order:

1. **Environment variables** (prefix `EPORT_ORCH_`)
2. **`parameters/parameters.yaml`** (local/dev fallback)
3. Hard-coded defaults (only for non-critical fields)

Key variables:

```bash
export EPORT_ORCH_DATA_API_BASE_URL="http://localhost:8001"
export EPORT_ORCH_GENERATION_API_BASE_URL="http://localhost:8003"
export EPORT_ORCH_ENVIRONMENT="local"    # local | dev | prod
export EPORT_ORCH_LOG_LEVEL="INFO"
export EPORT_ORCH_HTTP_TIMEOUT_SECONDS="15"
export EPORT_ORCH_GENERATION_TIMEOUT_SECONDS="60"
export EPORT_ORCH_MAX_RETRIES="2"
```

`parameters/parameters.yaml` contains sane defaults for local runs.

---

## 4. Endpoints

### `GET /healthz`

Simple liveness probe used by Cloud Run / monitoring.

**Response:**

```json
{
  "status": "ok",
  "service": "eport_orchestrator_api"
}
```

### `POST /v1/orchestrator/generate-cv`

High-level CV generation entry point.

**Request (simplified):**

```json
{
  "student_id": "U-1001",
  "role_id": "role%23ai_engineer",
  "jd_id": "jd%23ai_lead_gov_2025",
  "template_id": "T_EMPLOYER_STD_V3",
  "language": "en",
  "language_tone": "formal",
  "sections": ["profile_summary", "skills", "experience"],
  "user_input_cv_text_by_section": {
    "profile_summary": "Custom summary (optional)"
  },
  "user_or_llm_comments": {
    "user_comments": {
      "profile_summary": "Please emphasize research experience"
    }
  },
  "request_metadata": {
    "channel": "eport-ui",
    "request_id": "REQ-2025-00001"
  }
}
```

**Response (simplified):**

```json
{
  "status": "success",
  "cv": {
    "job_id": "JOB_U-1001_2025-01-01",
    "template_id": "T_EMPLOYER_STD_V3",
    "language": "en",
    "language_tone": "formal",
    "rendered_html": "<html>...</html>",
    "rendered_markdown": null,
    "sections": {
      "profile_summary": "...",
      "skills": "...",
      "experience": "..."
    },
    "raw_generation_result": { "...": "full Stage-D JSON" }
  },
  "error": null,
  "user_or_llm_comments": {
    "user_comments": {
      "profile_summary": "Please emphasize research experience"
    }
  },
  "request_metadata": {
    "channel": "eport-ui",
    "request_id": "REQ-2025-00001"
  }
}
```

On error, `status="error"` and `error` is populated with a `code`, `message`, and optional `details`.

---

## 5. Local Development

### 5.1 Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

Make sure `eport_data_api` and `eport_generation` are running locally (e.g., on ports `8001` and `8003`).

### 5.2 Run the API

```bash
uvicorn api:app --reload --port 8002
```

Check:

```bash
curl http://localhost:8002/healthz
```

---

## 6. Testing

```bash
pytest -q
```

Current tests:

* `test_healthz` – liveness endpoint.
* `test_generate_cv_success` – happy-path orchestration (generation call is monkeypatched).

---

## 7. Deployment (Cloud Run)

High-level steps (mirrors other services):

```bash
gcloud builds submit --tag REGION-docker.pkg.dev/PROJECT/eport-orchestrator-api/service

gcloud run deploy eport-orchestrator-api \
  --image=REGION-docker.pkg.dev/PROJECT/eport-orchestrator-api/service \
  --platform=managed \
  --region=REGION \
  --allow-unauthenticated
```

Configure env vars:

```bash
gcloud run services update eport-orchestrator-api \
  --update-env-vars=\
EPORT_ORCH_DATA_API_BASE_URL=https://eport-data-api-xxxx.a.run.app,\
EPORT_ORCH_GENERATION_API_BASE_URL=https://eport-generation-xxxx.a.run.app,\
EPORT_ORCH_ENVIRONMENT=prod
```

