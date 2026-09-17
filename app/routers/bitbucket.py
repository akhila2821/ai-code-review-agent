"""
Bitbucket webhook router.

Listens for pullrequest:created and pullrequest:updated events.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.models import Platform, PREvent
from app.services.ai_reviewer import review_diff
from app.services.diff_parser import diff_to_text, parse_diff
from app.services.platform.bitbucket import BitbucketClient
from app.services.report_generator import generate_inline_comment, generate_report
from app.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/webhook/bitbucket", tags=["Bitbucket"])

_client = BitbucketClient()

_REVIEW_EVENTS = {
    "pullrequest:created",
    "pullrequest:updated",
    "pullrequest:fulfilled",
}


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def bitbucket_webhook(
    request: Request,
    x_hub_signature: str = Header(default=""),
    x_event_key: str = Header(default=""),
) -> dict:
    """
    Receive and process Bitbucket webhook events.

    Only pullrequest:created and pullrequest:updated trigger reviews.
    """
    payload_bytes = await request.body()

    if not _client.verify_webhook_signature(payload_bytes, x_hub_signature):
        log.warning("Bitbucket webhook signature verification failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    if x_event_key not in _REVIEW_EVENTS:
        return {"status": "ignored", "reason": f"event={x_event_key}"}

    payload = await request.json()
    pr_data = payload.get("pullrequest", {})
    repo_data = payload.get("repository", {})

    event = PREvent(
        platform=Platform.BITBUCKET,
        repo_full_name=repo_data.get("full_name", ""),
        pr_number=pr_data.get("id", 0),
        pr_title=pr_data.get("title", ""),
        pr_description=pr_data.get("description") or "",
        head_sha=pr_data.get("source", {}).get("commit", {}).get("hash", ""),
        base_sha=pr_data.get("destination", {}).get("commit", {}).get("hash", ""),
        author=pr_data.get("author", {}).get("nickname", ""),
    )

    log.info(
        "Bitbucket PR review triggered: repo=%s pr=%d event=%s",
        event.repo_full_name,
        event.pr_number,
        x_event_key,
    )

    await _run_review(event)
    return {"status": "accepted", "pr": event.pr_number}


async def _run_review(event: PREvent) -> None:
    """Fetch diff, call AI reviewer, post comments."""
    try:
        raw_diff = await _client.get_pr_diff(event)
        file_diffs = parse_diff(raw_diff)
        diff_text = diff_to_text(file_diffs)

        result = await review_diff(
            diff_text=diff_text,
            pr_title=event.pr_title,
            pr_description=event.pr_description,
        )

        all_findings = (
            result.bugs + result.security + result.style
            + result.improvements + result.test_gaps
        )
        for finding in all_findings:
            if finding.line:
                await _client.post_inline_comment(
                    event=event,
                    filename=finding.file,
                    line=finding.line,
                    body=generate_inline_comment(finding),
                )

        report = generate_report(result, pr_title=event.pr_title)
        await _client.post_summary_comment(event, report)

        log.info(
            "Bitbucket review complete: pr=%d score=%d findings=%d",
            event.pr_number,
            result.score,
            result.total_findings,
        )
    except Exception as exc:
        log.error("Bitbucket review pipeline failed: %s", exc, exc_info=True)
