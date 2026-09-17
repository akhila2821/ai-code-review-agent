"""
GitHub webhook router.

Listens for pull_request events (opened, synchronize, reopened) and
triggers the AI review pipeline.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.models import Platform, PREvent
from app.services.ai_reviewer import review_diff
from app.services.diff_parser import diff_to_text, parse_diff
from app.services.platform.github import GitHubClient
from app.services.report_generator import generate_inline_comment, generate_report
from app.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/webhook/github", tags=["GitHub"])

_client = GitHubClient()

# PR actions that should trigger a review
_REVIEW_ACTIONS = {"opened", "synchronize", "reopened"}


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request,
    x_github_event: str = Header(default=""),
    x_hub_signature_256: str = Header(default=""),
) -> dict:
    """
    Receive and process GitHub webhook events.

    Only pull_request events with actions in {opened, synchronize, reopened}
    trigger a review. All others are acknowledged but ignored.
    """
    payload_bytes = await request.body()

    # ── Signature verification ────────────────────────────────────────────────
    if not _client.verify_webhook_signature(payload_bytes, x_hub_signature_256):
        log.warning("GitHub webhook signature verification failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    if x_github_event != "pull_request":
        return {"status": "ignored", "reason": f"event={x_github_event}"}

    payload = await request.json()
    action = payload.get("action", "")

    if action not in _REVIEW_ACTIONS:
        return {"status": "ignored", "reason": f"action={action}"}

    pr_data = payload.get("pull_request", {})
    repo_data = payload.get("repository", {})

    event = PREvent(
        platform=Platform.GITHUB,
        repo_full_name=repo_data.get("full_name", ""),
        pr_number=pr_data.get("number", 0),
        pr_title=pr_data.get("title", ""),
        pr_description=pr_data.get("body") or "",
        head_sha=pr_data.get("head", {}).get("sha", ""),
        base_sha=pr_data.get("base", {}).get("sha", ""),
        author=pr_data.get("user", {}).get("login", ""),
    )

    log.info(
        "GitHub PR review triggered: repo=%s pr=%d action=%s",
        event.repo_full_name,
        event.pr_number,
        action,
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

        # Post inline comments for each finding that has a line number
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

        # Post full summary report
        report = generate_report(result, pr_title=event.pr_title)
        await _client.post_summary_comment(event, report)

        log.info(
            "GitHub review complete: pr=%d score=%d findings=%d",
            event.pr_number,
            result.score,
            result.total_findings,
        )
    except Exception as exc:
        log.error("GitHub review pipeline failed: %s", exc, exc_info=True)
