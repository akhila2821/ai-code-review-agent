"""
Pydantic models for webhook payloads, review findings, and API responses.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────────────────────────

class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Platform(str, Enum):
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"


# ──────────────────────────────────────────────────────────────────────────────
# Review finding models
# ──────────────────────────────────────────────────────────────────────────────

class Finding(BaseModel):
    file: str
    line: int | None = None
    severity: Severity = Severity.MEDIUM
    message: str
    suggestion: str = ""


class ReviewResult(BaseModel):
    summary: str
    score: int = Field(ge=0, le=100)
    bugs: list[Finding] = []
    security: list[Finding] = []
    style: list[Finding] = []
    improvements: list[Finding] = []
    test_gaps: list[Finding] = []
    praise: list[str] = []

    @property
    def total_findings(self) -> int:
        return (
            len(self.bugs)
            + len(self.security)
            + len(self.style)
            + len(self.improvements)
            + len(self.test_gaps)
        )

    @property
    def has_critical_issues(self) -> bool:
        all_findings = self.bugs + self.security + self.style + self.improvements
        return any(f.severity == Severity.CRITICAL for f in all_findings)


# ──────────────────────────────────────────────────────────────────────────────
# Diff / hunk models
# ──────────────────────────────────────────────────────────────────────────────

class DiffHunk(BaseModel):
    """A single changed block within a file."""
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[str]


class FileDiff(BaseModel):
    """All diff hunks for a single file."""
    filename: str
    old_filename: str | None = None  # set when file was renamed
    status: str = "modified"         # added | modified | deleted | renamed
    hunks: list[DiffHunk] = []
    raw_diff: str = ""


# ──────────────────────────────────────────────────────────────────────────────
# Webhook event models (minimal — full payloads are passed as raw dicts)
# ──────────────────────────────────────────────────────────────────────────────

class PREvent(BaseModel):
    platform: Platform
    repo_full_name: str
    pr_number: int
    pr_title: str = ""
    pr_description: str = ""
    head_sha: str = ""
    base_sha: str = ""
    author: str = ""
    raw_payload: dict[str, Any] = Field(default_factory=dict, exclude=True)


# ──────────────────────────────────────────────────────────────────────────────
# API response models
# ──────────────────────────────────────────────────────────────────────────────

class ReviewResponse(BaseModel):
    status: str = "ok"
    platform: Platform
    repo: str
    pr_number: int
    score: int
    total_findings: int
    summary: str


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "1.0.0"
