"""
Abstract base class for platform clients (GitHub, GitLab, Bitbucket).
All platform implementations must implement this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from app.models import PREvent


class BasePlatformClient(ABC):
    """
    Common interface that every platform client must implement.
    """

    @abstractmethod
    async def get_pr_diff(self, event: PREvent) -> str:
        """Fetch the unified diff text for the PR/MR."""

    @abstractmethod
    async def post_summary_comment(self, event: PREvent, body: str) -> None:
        """Post a top-level comment on the PR/MR with the full review report."""

    @abstractmethod
    async def post_inline_comment(
        self,
        event: PREvent,
        filename: str,
        line: int,
        body: str,
    ) -> None:
        """Post an inline review comment on a specific file and line."""

    @abstractmethod
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify the webhook delivery signature.

        Returns True if valid, False otherwise.
        Implementations should use HMAC-SHA256 or the platform's equivalent.
        """
