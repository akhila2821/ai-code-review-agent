"""
GitLab webhook router.

Listens for Merge Request events and triggers the AI review pipeline.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.models import Platform, PREvent
from app.services.ai_reviewer import review_diff
from app.services.diff_parser import diff_to_text, parse_diff
from app.services.platform.gitlab import GitLabClient
from app.services.report_generator import generate_inline_comment, generate_report
from app.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/webhook/gitlab", tags=["GitLab"])

_client = GitLabClient()

_REVIEW_ACTIONS = {"open", "reopen", "update"}


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def gitlab_webhook(
    request: Request,
    x_gitlab_token: str = Header(default=""),
    x_gitlab_event: str = Header(default=""),
) -> dict:
    """
    Receive and process GitLab webhook events.

    Only 'Merge Request Hook' events with open/reopen/update actions trigger reviews.
    """
    payload_bytes = await request.body()

    if not _client.verify_webhook_signature(payload_bytes, x_gitlab_token):
        log.warning("GitLab webhook token verification failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook token",
        )

    if "Merge Request" not in x_gitlab_event:
        return {"status": "ignored", "reason": f"event={x_gitlab_event}"}

    payload = await request.json()
    attrs = payload.get("object_attributes", {})
    action = attrs.get("action", "")

    if action not in _REVIEW_ACTIONS:
        return {"status": "ignored", "reason": f"action={action}"}

    project = payload.get("project", {})
    event = PREvent(
        platform=Platform.GITLAB,
        repo_full_name=project.get("path_with_namespace", ""),
        pr_number=attrs.get("iid", 0),
        pr_title=attrs.get("title", ""),
        pr_description=attrs.get("description") or "",
        head_sha=attrs.get("last_commit", {}).get("id", ""),
        base_sha="",
        author=payload.get("user", {}).get("username", ""),
    )

    log.info(
        "GitLab MR review triggered: repo=%s mr=%d action=%s",
        event.repo_full_name,
        event.pr_number,
        action,
    )

    await _run_review(event)
    return {"status": "accepted", "mr": event.pr_number}


async def _run_review(event: PREvent) -> None:
    """Fetch diff, call AI reviewer, post notes."""
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
            "GitLab review complete: mr=%d score=%d findings=%d",
            event.pr_number,
            result.score,
            result.total_findings,
        )
    except Exception as exc:
        log.error("GitLab review pipeline failed: %s", exc, exc_info=True)
