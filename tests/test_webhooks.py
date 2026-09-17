"""
Integration tests for all three webhook endpoints.
Uses FastAPI's TestClient (via httpx) — no real platform calls are made.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _github_sig(payload: bytes, secret: str = "test-secret") -> str:
    return "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


GITHUB_PR_PAYLOAD = {
    "action": "opened",
    "pull_request": {
        "number": 42,
        "title": "Test PR",
        "body": "A test pull request.",
        "head": {"sha": "abc123"},
        "base": {"sha": "def456"},
        "user": {"login": "dev-user"},
    },
    "repository": {"full_name": "owner/repo"},
}

GITLAB_MR_PAYLOAD = {
    "object_kind": "merge_request",
    "user": {"username": "dev-user"},
    "project": {"path_with_namespace": "owner/repo"},
    "object_attributes": {
        "iid": 7,
        "title": "Test MR",
        "description": "A test merge request.",
        "action": "open",
        "last_commit": {"id": "abc123"},
    },
}

BITBUCKET_PR_PAYLOAD = {
    "pullrequest": {
        "id": 99,
        "title": "Test BB PR",
        "description": "A Bitbucket PR.",
        "author": {"nickname": "dev-user"},
        "source": {"commit": {"hash": "abc123"}},
        "destination": {"commit": {"hash": "def456"}},
    },
    "repository": {"full_name": "owner/repo"},
}


# ──────────────────────────────────────────────────────────────────────────────
# Health / Root
# ──────────────────────────────────────────────────────────────────────────────

def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_root_endpoint():
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "github" in data["webhooks"]


# ──────────────────────────────────────────────────────────────────────────────
# GitHub webhook
# ──────────────────────────────────────────────────────────────────────────────

def test_github_webhook_ignored_event():
    payload = json.dumps(GITHUB_PR_PAYLOAD).encode()
    resp = client.post(
        "/webhook/github",
        content=payload,
        headers={
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": _github_sig(payload),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "ignored"


def test_github_webhook_ignored_action():
    data = {**GITHUB_PR_PAYLOAD, "action": "closed"}
    payload = json.dumps(data).encode()
    resp = client.post(
        "/webhook/github",
        content=payload,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": _github_sig(payload),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "ignored"


@patch("app.routers.github._run_review", new_callable=AsyncMock)
@patch("app.routers.github._client.verify_webhook_signature", return_value=True)
def test_github_webhook_triggers_review(mock_sig, mock_review):
    payload = json.dumps(GITHUB_PR_PAYLOAD).encode()
    resp = client.post(
        "/webhook/github",
        content=payload,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "sha256=fake",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted"
    mock_review.assert_awaited_once()


# ──────────────────────────────────────────────────────────────────────────────
# GitLab webhook
# ──────────────────────────────────────────────────────────────────────────────

@patch("app.routers.gitlab._run_review", new_callable=AsyncMock)
@patch("app.routers.gitlab._client.verify_webhook_signature", return_value=True)
def test_gitlab_webhook_triggers_review(mock_sig, mock_review):
    payload = json.dumps(GITLAB_MR_PAYLOAD).encode()
    resp = client.post(
        "/webhook/gitlab",
        content=payload,
        headers={
            "X-Gitlab-Token": "test-secret",
            "X-Gitlab-Event": "Merge Request Hook",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted"
    mock_review.assert_awaited_once()


# ──────────────────────────────────────────────────────────────────────────────
# Bitbucket webhook
# ──────────────────────────────────────────────────────────────────────────────

@patch("app.routers.bitbucket._run_review", new_callable=AsyncMock)
@patch("app.routers.bitbucket._client.verify_webhook_signature", return_value=True)
def test_bitbucket_webhook_triggers_review(mock_sig, mock_review):
    payload = json.dumps(BITBUCKET_PR_PAYLOAD).encode()
    resp = client.post(
        "/webhook/bitbucket",
        content=payload,
        headers={
            "X-Hub-Signature": "sha256=fake",
            "X-Event-Key": "pullrequest:created",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted"
    mock_review.assert_awaited_once()
