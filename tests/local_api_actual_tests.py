"""
Local integration tests for eport_orchestrator_api.

⚠️ REQUIREMENTS
- Orchestrator API must be running locally:
    uvicorn api:app --reload --port 8002

These tests make REAL HTTP calls to:
    http://127.0.0.1:8002

They are intentionally NOT mocked and NOT meant for CI.
"""

import json
import sys
import httpx


BASE_URL = "http://127.0.0.1:8002"
HEADERS = {
    "Content-Type": "application/json",
    "X-API-Version": "1",
}


def pretty(resp: httpx.Response) -> None:
    print(f"\nSTATUS: {resp.status_code}")
    print("HEADERS:")
    for k, v in resp.headers.items():
        if k.lower().startswith("x-"):
            print(f"  {k}: {v}")
    try:
        print("BODY:")
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
    except Exception:
        print(resp.text)


# ---------------------------------------------------------------------
# 1) Health check
# ---------------------------------------------------------------------
def test_healthz() -> None:
    print("\n=== TEST 1: GET /healthz ===")
    resp = httpx.get(f"{BASE_URL}/healthz")
    pretty(resp)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


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
            "source": "local_api_test",
            "variant": "snake_case",
        },
    }

    resp = httpx.post(
        f"{BASE_URL}/api/v1/cv-generations",
        headers=HEADERS,
        json=payload,
        timeout=60,
    )
    pretty(resp)

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "success"
    assert "cv" in body
    assert "jobId" in body["cv"]  # camelCase response
    assert resp.headers.get("X-Correlation-Id")
    assert resp.headers.get("X-API-Version") == "1"


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
            "source": "local_api_test",
            "variant": "camelCase",
        },
    }

    resp = httpx.post(
        f"{BASE_URL}/api/v1/cv-generations",
        headers=HEADERS,
        json=payload,
        timeout=60,
    )
    pretty(resp)

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "success"
    assert body["cv"]["languageTone"] == "neutral"
    assert "userOrLlmComments" in body
    assert resp.headers.get("X-Correlation-Id")
    assert resp.headers.get("X-API-Version") == "1"


# ---------------------------------------------------------------------
# Entry point (run as script)
# ---------------------------------------------------------------------
if __name__ == "__main__":
    try:
        test_healthz()
        test_create_cv_generation_snake_case()
        test_create_cv_generation_camel_case()
    except AssertionError as e:
        print("\nTEST FAILED")
        raise
    except Exception as e:
        print("\nERROR:", e)
        sys.exit(1)

    print("\nALL LOCAL API TESTS PASSED")
