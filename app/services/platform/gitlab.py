"""
GitLab platform client.

Uses python-gitlab for API access and token comparison for webhook verification.
"""

from __future__ import annotations

import hashlib
import hmac

import gitlab
from gitlab.v4.cli import GitlabCLI  # noqa: F401 — triggers import check

from app.config import get_settings
from app.models import PREvent
from app.services.platform.base import BasePlatformClient
from app.utils.logger import get_logger

log = get_logger(__name__)
settings = get_settings()


class GitLabClient(BasePlatformClient):
    """GitLab platform client backed by python-gitlab."""

    def __init__(self) -> None:
        self._gl = gitlab.Gitlab(
            url=settings.gitlab_url,
            private_token=settings.gitlab_token,
        )

    def _get_mr(self, event: PREvent):
        project = self._gl.projects.get(event.repo_full_name)
        return project.mergerequests.get(event.pr_number)

    # ── Interface implementation ──────────────────────────────────────────────

    async def get_pr_diff(self, event: PREvent) -> str:
        """Fetch diff via GitLab MR diffs API."""
        import httpx

        encoded_path = event.repo_full_name.replace("/", "%2F")
        url = (
            f"{settings.gitlab_url}/api/v4/projects/{encoded_path}"
            f"/merge_requests/{event.pr_number}/diffs"
        )
        headers = {"PRIVATE-TOKEN": settings.gitlab_token}

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            diffs = response.json()

        # Concatenate all file diffs into unified diff format
        parts: list[str] = []
        for d in diffs:
            parts.append(
                f"diff --git a/{d['old_path']} b/{d['new_path']}\n"
                f"--- a/{d['old_path']}\n"
                f"+++ b/{d['new_path']}\n"
                f"{d.get('diff', '')}"
            )
        return "\n".join(parts)

    async def post_summary_comment(self, event: PREvent, body: str) -> None:
        """Post a review summary as an MR note."""
        try:
            mr = self._get_mr(event)
            mr.notes.create({"body": body})
            log.info(
                "Posted summary comment on GitLab MR !%d in %s",
                event.pr_number,
                event.repo_full_name,
            )
        except Exception as exc:
            log.error("GitLab post_summary_comment failed: %s", exc)
            raise

    async def post_inline_comment(
        self,
        event: PREvent,
        filename: str,
        line: int,
        body: str,
    ) -> None:
        """Post an inline note on a specific file and line via the Discussions API."""
        try:
            mr = self._get_mr(event)
            mr.discussions.create(
                {
                    "body": body,
                    "position": {
                        "position_type": "text",
                        "new_path": filename,
                        "new_line": line,
                        "base_sha": event.base_sha,
                        "head_sha": event.head_sha,
                        "start_sha": event.base_sha,
                    },
                }
            )
            log.debug(
                "Posted inline comment on %s:%d (MR !%d)",
                filename,
                line,
                event.pr_number,
            )
        except Exception as exc:
            log.warning(
                "GitLab inline comment failed for %s:%d — %s", filename, line, exc
            )

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        GitLab sends the webhook secret as the X-Gitlab-Token header (plain text).

        Args:
            payload: Raw request body (unused for GitLab).
            signature: Value of X-Gitlab-Token header.
        """
        if not settings.gitlab_webhook_secret:
            log.warning("No GitLab webhook secret configured — skipping verification")
            return True
        return hmac.compare_digest(settings.gitlab_webhook_secret, signature)
