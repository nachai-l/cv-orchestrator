"""
GCP (Cloud Run) smoke tests for eport_orchestrator_api.

⚠️ REQUIREMENTS
- Cloud Run service must already be deployed and reachable.
- These tests make REAL HTTP calls to the deployed service URL.
- Not meant for CI unless you explicitly want it.

Default target:
    https://cv-orchestrator-810737581373.asia-southeast1.run.app

Override via env var:
    ORCH_BASE_URL=https://... python tests/gcp_api_actual_tests.py
"""

from __future__ import annotations

import json
import os
import sys
import httpx

DEFAULT_BASE_URL = "https://cv-orchestrator-810737581373.asia-southeast1.run.app"
BASE_URL = os.getenv("ORCH_BASE_URL", DEFAULT_BASE_URL).rstrip("/")

HEADERS = {
    "Content-Type": "application/json",
    "X-API-Version": "1",
}


def pretty(resp: httpx.Response) -> None:
    print(f"\nSTATUS: {resp.status_code}")
    print("HEADERS (selected):")
    for k, v in resp.headers.items():
        lk = k.lower()
        # show useful Cloud Run / API headers
        if lk.startswith("x-") or lk in {"date", "server", "content-type"}:
            print(f"  {k}: {v}")
    try:
        print("BODY:")
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
    except Exception:
        print(resp.text)


def _assert_common_headers(resp: httpx.Response) -> None:
    # These should be present on success and errors (per your middleware/handlers)
    assert resp.headers.get("X-Correlation-Id"), "missing X-Correlation-Id"
    assert resp.headers.get("X-API-Version") == "1", "X-API-Version should be '1'"


# ---------------------------------------------------------------------
# 1) Health check
# ---------------------------------------------------------------------
def test_health() -> None:
    print(f"\n=== TEST 1: GET /health @ {BASE_URL} ===")
    resp = httpx.get(f"{BASE_URL}/health", timeout=30)
    pretty(resp)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "service" in data
    assert "environment" in data


# ---------------------------------------------------------------------
# 2) REST endpoint — snake_case request
# ---------------------------------------------------------------------
def test_create_cv_generation_snake_case() -> None:
    print("\n=== TEST 2: POST /api/v1/cv-generations (snake_case) ===")

    payload = {
        "student_id": "U-1001",
        "template_id": "T_EMPLOYER_STD_V3",
        "language": "en",
        "language_tone": "formal",
        "sections": ["profile_summary"],
        "request_metadata": {
            "source": "gcp_api_test",
            "variant": "snake_case",
        },
    }

    resp = httpx.post(
        f"{BASE_URL}/api/v1/cv-generations",
        headers=HEADERS,
        json=payload,
        timeout=180,  # allow for real downstream calls
    )
    pretty(resp)
    _assert_common_headers(resp)

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "success"
    assert "cv" in body
    assert "jobId" in body["cv"]  # camelCase response
    assert body["cv"]["templateId"] == "T_EMPLOYER_STD_V3"


# ---------------------------------------------------------------------
# 3) REST endpoint — camelCase request
# ---------------------------------------------------------------------
def test_create_cv_generation_camel_case() -> None:
    print("\n=== TEST 3: POST /api/v1/cv-generations (camelCase) ===")

    payload = {
        "studentId": "U-1001",
        "templateId": "T_EMPLOYER_STD_V3",
        "language": "en",
        "languageTone": "neutral",
        "sections": ["profile_summary"],
        "userOrLlmComments": {
            "profile_summary": "Focus on leadership and impact",
        },
        "requestMetadata": {
            "source": "gcp_api_test",
            "variant": "camelCase",
        },
    }

    resp = httpx.post(
        f"{BASE_URL}/api/v1/cv-generations",
        headers=HEADERS,
        json=payload,
        timeout=180,
    )
    pretty(resp)
    _assert_common_headers(resp)

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "success"
    assert body["cv"]["languageTone"] == "neutral"
    assert "userOrLlmComments" in body


# ---------------------------------------------------------------------
# Optional: negative test for versioning
# ---------------------------------------------------------------------
def test_invalid_api_version_returns_400() -> None:
    print("\n=== TEST 4: POST /api/v1/cv-generations (invalid X-API-Version) ===")

    payload = {
        "studentId": "U-1001",
        "templateId": "T_EMPLOYER_STD_V3",
        "language": "en",
        "sections": ["profile_summary"],
    }

    bad_headers = dict(HEADERS)
    bad_headers["X-API-Version"] = "2"

    resp = httpx.post(
        f"{BASE_URL}/api/v1/cv-generations",
        headers=bad_headers,
        json=payload,
        timeout=60,
    )
    pretty(resp)

    assert resp.status_code == 400
    # error schema is camelCase
    body = resp.json()
    assert body["code"] == "INVALID_FIELD_VALUE"
    assert body["correlationId"]
    assert resp.headers.get("X-Correlation-Id")
    assert resp.headers.get("X-API-Version") == "1"  # middleware forces default for errors


# ---------------------------------------------------------------------
# Entry point (run as script)
# ---------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Running GCP smoke tests against: {BASE_URL}")

    try:
        test_healthz()
        test_create_cv_generation_snake_case()
        test_create_cv_generation_camel_case()
        test_invalid_api_version_returns_400()
    except AssertionError:
        print("\nTEST FAILED")
        raise
    except Exception as e:
        print("\nERROR:", e)
        sys.exit(1)

    print("\nALL GCP API TESTS PASSED ✅")
