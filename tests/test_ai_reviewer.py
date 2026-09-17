"""
Tests for the AI reviewer service.

Uses pytest-mock to patch the OpenAI client so no real API calls are made.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import Severity
from app.services.ai_reviewer import ReviewError, review_diff

MOCK_RESPONSE = {
    "summary": "The code looks generally good with a few minor issues.",
    "score": 82,
    "bugs": [
        {
            "file": "app/utils.py",
            "line": 15,
            "severity": "high",
            "message": "Potential division by zero.",
            "suggestion": "Add a guard: if divisor == 0: raise ValueError",
        }
    ],
    "security": [],
    "style": [
        {
            "file": "app/utils.py",
            "line": 10,
            "severity": "low",
            "message": "Missing type annotation on return value.",
            "suggestion": "Add -> None or appropriate return type.",
        }
    ],
    "improvements": [],
    "test_gaps": [
        {
            "file": "app/utils.py",
            "line": None,
            "severity": "medium",
            "message": "No test for division by zero edge case.",
            "suggestion": "Add a test asserting ValueError is raised.",
        }
    ],
    "praise": ["Good use of docstrings.", "Clean function names."],
}


def _make_mock_response(content: dict) -> MagicMock:
    """Build a mock openai response object."""
    choice = MagicMock()
    choice.message.content = json.dumps(content)
    mock_resp = MagicMock()
    mock_resp.choices = [choice]
    return mock_resp


@pytest.mark.asyncio
async def test_review_diff_returns_result():
    with patch("app.services.ai_reviewer._get_client") as mock_get_client:
        client = MagicMock()
        client.chat.completions.create = AsyncMock(
            return_value=_make_mock_response(MOCK_RESPONSE)
        )
        mock_get_client.return_value = client

        result = await review_diff(
            diff_text="+ some code change",
            pr_title="Fix division bug",
        )

    assert result.score == 82
    assert result.summary == MOCK_RESPONSE["summary"]
    assert len(result.bugs) == 1
    assert result.bugs[0].severity == Severity.HIGH
    assert result.bugs[0].line == 15
    assert len(result.style) == 1
    assert len(result.test_gaps) == 1
    assert result.test_gaps[0].line is None
    assert len(result.praise) == 2


@pytest.mark.asyncio
async def test_review_empty_diff_returns_default():
    result = await review_diff(diff_text="")
    assert result.score == 100
    assert result.total_findings == 0


@pytest.mark.asyncio
async def test_review_diff_raises_on_non_json():
    with patch("app.services.ai_reviewer._get_client") as mock_get_client:
        client = MagicMock()
        choice = MagicMock()
        choice.message.content = "This is not JSON at all!"
        resp = MagicMock()
        resp.choices = [choice]
        client.chat.completions.create = AsyncMock(return_value=resp)
        mock_get_client.return_value = client

        with pytest.raises(ReviewError):
            await review_diff(diff_text="+ code change")


@pytest.mark.asyncio
async def test_review_score_clamped():
    bad_response = {**MOCK_RESPONSE, "score": 150}
    with patch("app.services.ai_reviewer._get_client") as mock_get_client:
        client = MagicMock()
        client.chat.completions.create = AsyncMock(
            return_value=_make_mock_response(bad_response)
        )
        mock_get_client.return_value = client
        result = await review_diff(diff_text="+ code")

    assert result.score == 100  # clamped to 100
