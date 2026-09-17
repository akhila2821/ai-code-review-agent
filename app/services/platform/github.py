"""
GitHub platform client.

Uses PyGithub for API access and HMAC-SHA256 for webhook verification.
"""

from __future__ import annotations

import hashlib
import hmac

from github import Auth, Github, GithubException
from github.PullRequest import PullRequest

from app.config import get_settings
from app.models import PREvent
from app.services.platform.base import BasePlatformClient
from app.utils.logger import get_logger

log = get_logger(__name__)
settings = get_settings()


class GitHubClient(BasePlatformClient):
    """GitHub platform client backed by PyGithub."""

    def __init__(self) -> None:
        auth = Auth.Token(settings.github_token)
        self._gh = Github(auth=auth)

    def _get_pr(self, event: PREvent) -> PullRequest:
        repo = self._gh.get_repo(event.repo_full_name)
        return repo.get_pull(event.pr_number)

    # ── Interface implementation ──────────────────────────────────────────────

    async def get_pr_diff(self, event: PREvent) -> str:
        """Fetch unified diff via the GitHub Pulls API."""
        import httpx

        url = (
            f"https://api.github.com/repos/{event.repo_full_name}"
            f"/pulls/{event.pr_number}"
        )
        headers = {
            "Authorization": f"token {settings.github_token}",
            "Accept": "application/vnd.github.v3.diff",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.text

    async def post_summary_comment(self, event: PREvent, body: str) -> None:
        """Post a review summary as a PR issue comment."""
        try:
            pr = self._get_pr(event)
            pr.create_issue_comment(body)
            log.info(
                "Posted summary comment on GitHub PR #%d in %s",
                event.pr_number,
                event.repo_full_name,
            )
        except GithubException as exc:
            log.error("GitHub post_summary_comment failed: %s", exc)
            raise

    async def post_inline_comment(
        self,
        event: PREvent,
        filename: str,
        line: int,
        body: str,
    ) -> None:
        """Post an inline review comment on a specific line of the diff."""
        try:
            pr = self._get_pr(event)
            pr.create_review_comment(
                body=body,
                commit=pr.get_commits().reversed[0],
                path=filename,
                line=line,
            )
            log.debug(
                "Posted inline comment on %s:%d (PR #%d)",
                filename,
                line,
                event.pr_number,
            )
        except GithubException as exc:
            # Inline comments can fail if the line is not in the diff — log and continue
            log.warning(
                "Inline comment failed for %s:%d — %s", filename, line, exc
            )

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify GitHub's X-Hub-Signature-256 header.

        Args:
            payload: Raw request body bytes.
            signature: Value of the X-Hub-Signature-256 header (e.g. "sha256=abc123").

        Returns:
            True if the signature matches; False otherwise.
        """
        if not settings.github_webhook_secret:
            log.warning("No GitHub webhook secret configured — skipping verification")
            return True

        secret = settings.github_webhook_secret.encode()
        expected = "sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
