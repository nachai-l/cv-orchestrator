# E-Port Orchestrator API

**Backend-for-Frontend (BFF)** service that orchestrates end-to-end CV generation by coordinating:

* **E-Port Data API (`eport_data_api`)**
  Student profiles, role taxonomy, JD taxonomy, template metadata
* **E-Port Generation Service (`eport_generation`)**
  Stage A–D LLM-based CV generation pipeline

The Orchestrator exposes **one stable external API** and hides all internal data hydration and generation complexity.

---

## 1. Responsibilities

The Orchestrator API is responsible for:

1. **Validating external requests**

   * Accepts only identifiers and generation options
   * No raw profile data is accepted from clients

2. **Hydrating canonical data from `eport_data_api`**

   * `student_full_profile`
   * `role_taxonomy`
   * `jd_taxonomy`
   * `template_info`

3. **Assembling a validated Stage-0 payload**

   * Strictly aligned with `eport_generation.schemas.stage0_schema`
   * Performs normalization and consistency checks

4. **Calling the CV Generation Service**

   * Handles timeouts, retries, and error propagation
   * Returns a clean, stable response envelope

5. **Returning a unified `GenerateCVResponse`**

   * Includes generated CV sections
   * Preserves raw Stage-D output for auditing and debugging
   * Passes through user / LLM comments and request metadata

---

## 2. Project Structure

```
.
├── api.py                         # FastAPI app + public endpoints
├── functions/
│   ├── orchestrator/
│   │   ├── eport_orchestrator_service.py  # Core orchestration logic
│   │   ├── data_fetcher.py                # Calls eport_data_api
│   │   ├── profile_normalizer.py
│   │   ├── role_normalizer.py
│   │   └── job_normalizer.py
│   ├── utils/
│   │   ├── settings.py            # ENV + parameters.yaml loading
│   │   └── http_client.py         # Shared HTTP client utilities
│   └── models/                    # Reserved for future internal models
├── schemas/
│   ├── input_schema.py             # External request schema
│   ├── output_schema.py            # External response envelope
│   └── stage0_schema.py            # Internal Stage-0 payload
├── parameters/
│   └── parameters.yaml             # Local / dev config fallback
├── tests/
│   └── test_generate_cv_endpoint.py
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## 3. Configuration

Configuration is resolved in the following order:

1. **Environment variables** (highest priority)
2. `parameters/parameters.yaml` (local / dev fallback)
3. Hard-coded defaults (non-critical fields only)

### Key Environment Variables

```bash
ENVIRONMENT=prod                     # local | dev | prod

DATA_API_BASE_URL=https://eport-data-api-xxxx.a.run.app
GENERATION_API_BASE_URL=https://cv-generation-service-xxxx.a.run.app

HTTP_TIMEOUT_SECONDS=30
GENERATION_TIMEOUT_SECONDS=300
MAX_RETRIES=2
LOG_LEVEL=INFO
```

`parameters/parameters.yaml` provides sane defaults for local development.

---

## 4. API Endpoints

### 4.1 Health Check

**GET `/health`**

Used by Cloud Run and monitoring.

**Response**

```json
{
  "status": "ok",
  "service": "eport_orchestrator_api",
  "environment": "prod"
}
```

---

### 4.2 Generate CV

**POST `/v1/orchestrator/generate-cv`**

High-level CV generation entry point.

#### Request (simplified)

```json
{
  "student_id": "U-1001",
  "role_id": "role#ai_engineer",
  "jd_id": "jd#ai_lead_gov_2025",
  "template_id": "T_EMPLOYER_STD_V3",
  "language": "en",
  "language_tone": "formal",
  "sections": ["profile_summary", "skills", "experience", "education"],
  "user_input_cv_text_by_section": null,
  "user_or_llm_comments": {
    "profile_summary": "Please emphasize research experience"
  },
  "request_metadata": {
    "source": "cloud-run"
  }
}
```

#### Response (simplified)

```json
{
  "status": "success",
  "cv": {
    "job_id": "JOB_U-1001",
    "template_id": "T_EMPLOYER_STD_V3",
    "language": "en",
    "language_tone": "formal",
    "sections": {
      "profile_summary": { "...": "..." },
      "skills": { "...": "..." },
      "experience": { "...": "..." }
    },
    "raw_generation_result": { "...": "Full Stage-D JSON" }
  },
  "error": null,
  "user_or_llm_comments": {
    "profile_summary": "Please emphasize research experience"
  },
  "request_metadata": {
    "source": "cloud-run"
  }
}
```

#### Error Handling

* `status = "error"`
* `error.code`, `error.message`, and `error.details` populated
* Example:

  * Missing role skills
  * Invalid taxonomy
  * Downstream service timeout

---

## 5. Local Development

### 5.1 Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Ensure the following services are running locally:

* `eport_data_api` (e.g. `localhost:8001`)
* `eport_generation` (e.g. `localhost:8000`)

---

### 5.2 Run the API

```bash
uvicorn api:app --reload --port 8002
```

Verify:

```bash
curl http://localhost:8002/health
```

---

## 6. Testing

```bash
pytest -q
```

Current coverage:

* Health endpoint
* Happy-path CV generation (generation service mocked)

---

## 7. Deployment (Cloud Run)

### 7.1 Build & Push Image

```bash
gcloud builds submit \
  --tag asia-southeast1-docker.pkg.dev/PROJECT_ID/cv-orchestrator/service:latest
```

### 7.2 Deploy Service

```bash
gcloud run deploy cv-orchestrator \
  --image asia-southeast1-docker.pkg.dev/PROJECT_ID/cv-orchestrator/service:latest \
  --region asia-southeast1 \
  --platform managed \
  --service-account cv-orchestrator-sa@PROJECT_ID.iam.gserviceaccount.com
```

### 7.3 IAM (Invoker)

* **Internal-only access**: remove `allUsers`
* **Public access** (temporary / demo):

```bash
gcloud run services add-iam-policy-binding cv-orchestrator \
  --region asia-southeast1 \
  --member allUsers \
  --role roles/run.invoker
```

---

## 8. Current Status

✅ Deployed on Cloud Run
✅ End-to-end integration tested with Data API + Generation Service
✅ Stage-0 validation enforced
✅ Structured logs and request tracing enabled
🟡 Role / JD data quality enforced strictly (empty skills → hard error)

---

If you want, next we can:

* Add **architecture diagram**
* Add **IAM / security section**
* Add **timeout & retry design notes**
* Add **API contract versioning notes**

Just tell me.
