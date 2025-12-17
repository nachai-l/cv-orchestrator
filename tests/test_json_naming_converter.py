# tests/test_json_naming_converter.py
import pytest

from functions.utils.json_naming_converter import (
    snake_to_camel,
    convert_keys_snake_to_camel,
)


def test_smoke_discovery():
    # helps ensure pytest discovery isn't broken
    assert True


def test_snake_to_camel_basic():
    assert snake_to_camel("student_id") == "studentId"
    assert snake_to_camel("language_tone") == "languageTone"
    assert snake_to_camel("a_b_c") == "aBC"


def test_snake_to_camel_no_underscore_unchanged():
    assert snake_to_camel("status") == "status"
    assert snake_to_camel("jobId") == "jobId"


def test_snake_to_camel_preserves_leading_trailing_underscores():
    assert snake_to_camel("__private_field") == "__privateField"
    assert snake_to_camel("field__") == "field__"
    assert snake_to_camel("__") == "__"


def test_convert_keys_recursive_dict_and_list():
    src = {
        "status": "success",
        "request_metadata": {"source": "pytest", "trace_id": "t1"},
        "sections": [
            {"section_name": "profile_summary", "word_count": 10},
            {"section_name": "skills", "word_count": 5},
        ],
        "raw_generation_result": {
            "generated_at": "2025-01-01T00:00:00Z",
            "tokens_used": 123,
        },
    }

    out = convert_keys_snake_to_camel(src)

    assert out["status"] == "success"
    assert out["requestMetadata"]["source"] == "pytest"
    assert out["requestMetadata"]["traceId"] == "t1"
    assert out["sections"][0]["sectionName"] == "profile_summary"
    assert out["sections"][0]["wordCount"] == 10
    assert out["rawGenerationResult"]["generatedAt"] == "2025-01-01T00:00:00Z"
    assert out["rawGenerationResult"]["tokensUsed"] == 123


def test_convert_keys_keeps_primitives():
    assert convert_keys_snake_to_camel("x") == "x"
    assert convert_keys_snake_to_camel(1) == 1
    assert convert_keys_snake_to_camel(None) is None
    assert convert_keys_snake_to_camel(True) is True


def test_convert_keys_preserve_container_keys_inner_dict():
    """
    Matches old converter behavior:
    preserve_container_keys means:
      - convert the container key itself
      - DO NOT convert inner keys within that container value
    """
    src = {
        "user_or_llm_comments": {"profile_summary": "keep_this_key"},
        "request_metadata": {"trace_id": "t1"},
    }

    out = convert_keys_snake_to_camel(src, preserve_container_keys={"user_or_llm_comments"})

    # container key converted
    assert "userOrLlmComments" in out
    # inner key preserved (still snake_case)
    assert "profile_summary" in out["userOrLlmComments"]
    assert out["userOrLlmComments"]["profile_summary"] == "keep_this_key"

    # other dicts still converted normally
    assert out["requestMetadata"]["traceId"] == "t1"
