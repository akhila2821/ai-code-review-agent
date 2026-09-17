"""
Core AI review engine — calls GPT-4o and parses the structured response.
"""

from __future__ import annotations

import json

from openai import AsyncOpenAI, OpenAIError

from app.config import get_settings
from app.models import Finding, ReviewResult, Severity
from app.utils.logger import get_logger
from app.utils.prompts import build_review_messages

log = get_logger(__name__)
settings = get_settings()

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def review_diff(
    diff_text: str,
    pr_title: str = "",
    pr_description: str = "",
    extra_context: str = "",
) -> ReviewResult:
    """
    Send a diff to GPT-4o and return a structured ReviewResult.

    Args:
        diff_text: The unified diff string to review.
        pr_title: Optional PR title for extra context.
        pr_description: Optional PR body for extra context.
        extra_context: Any other relevant context (language, guidelines, etc.).

    Returns:
        ReviewResult parsed from the model's JSON response.

    Raises:
        ReviewError: On API failure or unparseable response.
    """
    if not diff_text.strip():
        log.warning("Empty diff passed to review_diff — returning empty result")
        return ReviewResult(summary="No changes detected.", score=100)

    messages = build_review_messages(
        diff=diff_text,
        pr_title=pr_title,
        pr_description=pr_description,
        extra_context=extra_context,
    )

    log.info(
        "Calling %s for review | pr_title=%r | diff_size=%d bytes",
        settings.openai_model,
        pr_title,
        len(diff_text),
    )

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,  # type: ignore[arg-type]
            max_tokens=settings.openai_max_tokens,
            temperature=settings.openai_temperature,
            response_format={"type": "json_object"},
        )
    except OpenAIError as exc:
        log.error("OpenAI API error: %s", exc)
        raise ReviewError(f"OpenAI API error: {exc}") from exc

    raw_content = response.choices[0].message.content or "{}"
    log.debug("Raw LLM response: %s", raw_content[:500])

    return _parse_response(raw_content)


def _parse_response(raw: str) -> ReviewResult:
    """Parse the JSON string returned by GPT-4o into a ReviewResult."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.error("Failed to parse LLM response as JSON: %s", exc)
        raise ReviewError("Model returned non-JSON response") from exc

    def parse_findings(items: list) -> list[Finding]:
        results = []
        for item in items or []:
            try:
                results.append(
                    Finding(
                        file=item.get("file", "unknown"),
                        line=item.get("line"),
                        severity=Severity(item.get("severity", "medium")),
                        message=item.get("message", ""),
                        suggestion=item.get("suggestion", ""),
                    )
                )
            except Exception as exc:
                log.warning("Skipping malformed finding: %s — %s", item, exc)
        return results

    praise_raw = data.get("praise", [])
    praise = [p if isinstance(p, str) else p.get("message", str(p)) for p in praise_raw]

    return ReviewResult(
        summary=data.get("summary", "Review complete."),
        score=max(0, min(100, int(data.get("score", 75)))),
        bugs=parse_findings(data.get("bugs", [])),
        security=parse_findings(data.get("security", [])),
        style=parse_findings(data.get("style", [])),
        improvements=parse_findings(data.get("improvements", [])),
        test_gaps=parse_findings(data.get("test_gaps", [])),
        praise=praise,
    )


class ReviewError(Exception):
    """Raised when the AI review fails."""
