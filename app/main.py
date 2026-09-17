"""
FastAPI application entrypoint.

Registers all webhook routers and serves a health-check endpoint.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import bitbucket, github, gitlab
from app.utils.logger import configure_logging, get_logger

configure_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("🚀 AI Code Review Agent starting up…")
    yield
    log.info("🛑 AI Code Review Agent shutting down.")


app = FastAPI(
    title="AI Code Review Agent",
    description=(
        "An AI-powered code review service backed by GPT-4o. "
        "Supports GitHub, GitLab, and Bitbucket webhooks plus a local CLI."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Allow all origins in development; tighten in production via env
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(github.router)
app.include_router(gitlab.router)
app.include_router(bitbucket.router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health() -> dict:
    """Liveness probe — returns HTTP 200 when the service is running."""
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/", tags=["Health"])
async def root() -> dict:
    return {
        "service": "AI Code Review Agent",
        "version": "1.0.0",
        "docs": "/docs",
        "webhooks": {
            "github": "/webhook/github",
            "gitlab": "/webhook/gitlab",
            "bitbucket": "/webhook/bitbucket",
        },
    }
