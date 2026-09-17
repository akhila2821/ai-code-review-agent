"""
Bitbucket platform client.

Uses the Bitbucket REST API v2 via httpx (async).
Webhook verification uses HMAC-SHA256 with the configured secret.
"""

from __future__ import annotations

import hashlib
import hmac

import httpx

from app.config import get_settings
from app.models import PREvent
from app.services.platform.base import BasePlatformClient
from app.utils.logger import get_logger

log = get_logger(__name__)
settings = get_settings()

_BB_BASE = "https://api.bitbucket.org/2.0"


class BitbucketClient(BasePlatformClient):
    """Bitbucket platform client using the REST API v2."""

    def _auth(self) -> httpx.BasicAuth:
        return httpx.BasicAuth(
            settings.bitbucket_username, settings.bitbucket_app_password
        )

    def _pr_url(self, event: PREvent) -> str:
        return (
            f"{_BB_BASE}/repositories/{event.repo_full_name}"
            f"/pullrequests/{event.pr_number}"
        )

    # ── Interface implementation ──────────────────────────────────────────────

    async def get_pr_diff(self, event: PREvent) -> str:
        """Fetch unified diff from Bitbucket's /diff endpoint."""
        url = f"{self._pr_url(event)}/diff"
        async with httpx.AsyncClient(auth=self._auth(), timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    async def post_summary_comment(self, event: PREvent, body: str) -> None:
        """Post a general comment on the PR."""
        url = f"{self._pr_url(event)}/comments"
        payload = {"content": {"raw": body}}

        async with httpx.AsyncClient(auth=self._auth(), timeout=30) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

        log.info(
            "Posted summary comment on Bitbucket PR #%d in %s",
            event.pr_number,
            event.repo_full_name,
        )

    async def post_inline_comment(
        self,
        event: PREvent,
        filename: str,
        line: int,
        body: str,
    ) -> None:
        """Post an inline comment anchored to a specific file and line."""
        url = f"{self._pr_url(event)}/comments"
        payload = {
            "content": {"raw": body},
            "inline": {
                "path": filename,
                "to": line,
            },
        }

        try:
            async with httpx.AsyncClient(auth=self._auth(), timeout=30) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
            log.debug(
                "Posted inline comment on %s:%d (PR #%d)",
                filename,
                line,
                event.pr_number,
            )
        except httpx.HTTPStatusError as exc:
            log.warning(
                "Bitbucket inline comment failed for %s:%d — %s",
                filename,
                line,
                exc,
            )

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify Bitbucket's X-Hub-Signature header (HMAC-SHA256).

        Args:
            payload: Raw request body bytes.
            signature: Value of X-Hub-Signature header (format: "sha256=<hex>").
        """
        if not settings.bitbucket_webhook_secret:
            log.warning("No Bitbucket webhook secret configured — skipping verification")
            return True

        secret = settings.bitbucket_webhook_secret.encode()
        expected = "sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
