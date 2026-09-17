# 🤖 AI Code Review Agent

> An AI-powered code review service backed by **GPT-4o** that automatically reviews Pull Requests on GitHub, GitLab, and Bitbucket — and can also be run locally via CLI.

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)](https://fastapi.tiangolo.com)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-purple)](https://openai.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## ✨ Features

| Feature | Description |
|---|---|
| 🐛 **Bug Detection** | Identifies logic errors and runtime risks |
| 🔒 **Security Scanning** | Flags injection risks, hardcoded secrets, insecure patterns |
| 🎨 **Style & Linting** | Catches style violations and naming inconsistencies |
| 💡 **Refactoring Hints** | Suggests cleaner, more idiomatic implementations |
| 🧪 **Test Coverage Gaps** | Highlights untested paths and missing edge-case tests |
| 📝 **Summary Report** | Posts a structured Markdown report as a PR comment |
| 💬 **Inline Comments** | Posts per-line comments directly in the PR diff |
| 🏆 **Quality Score** | 0–100 score for each PR |

---

## 🏗️ Architecture

```
ai-code-review-agent/
├── app/
│   ├── main.py                  # FastAPI entrypoint
│   ├── config.py                # Pydantic settings
│   ├── models.py                # Data models
│   ├── routers/                 # Webhook handlers (GitHub / GitLab / Bitbucket)
│   ├── services/
│   │   ├── ai_reviewer.py       # GPT-4o review engine
│   │   ├── diff_parser.py       # Unified diff parser
│   │   ├── report_generator.py  # Markdown report builder
│   │   └── platform/            # Platform API clients
│   └── utils/                   # Prompts & logging
├── cli/
│   └── review.py                # Local CLI tool
├── tests/                       # pytest test suite
├── .github/workflows/           # GitHub Actions self-review
├── Dockerfile
└── docker-compose.yml
```

---

## 🚀 Quick Start

### 1. Clone & configure

```bash
git clone https://github.com/akhila2821/ai-code-review-agent.git
cd ai-code-review-agent
cp .env.example .env
# Edit .env and fill in your API keys
```

### 2. Install dependencies

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Run the server

```bash
uvicorn app.main:app --reload --port 8000
```

Or with Docker:

```bash
docker-compose up --build
```

The API docs are available at **http://localhost:8000/docs**

---

## 🔌 Webhook Setup

### GitHub

1. Go to your repo → **Settings → Webhooks → Add webhook**
2. Set the Payload URL to `https://your-server.com/webhook/github`
3. Content type: `application/json`
4. Secret: the value from `GITHUB_WEBHOOK_SECRET` in your `.env`
5. Events: select **Pull requests**

### GitLab

1. Go to your project → **Settings → Webhooks**
2. URL: `https://your-server.com/webhook/gitlab`
3. Secret Token: the value from `GITLAB_WEBHOOK_SECRET`
4. Trigger: check **Merge request events**

### Bitbucket

1. Go to your repo → **Repository settings → Webhooks**
2. URL: `https://your-server.com/webhook/bitbucket`
3. Events: select **Pull Request: Created** and **Pull Request: Updated**

> 💡 For local testing, use [ngrok](https://ngrok.com): `ngrok http 8000`

---

## 💻 Local CLI Usage

Review a **single file**:
```bash
python -m cli.review file --file path/to/myfile.py
```

Review a **patch / diff file**:
```bash
python -m cli.review diff --diff changes.patch
```

Review a **git branch diff**:
```bash
python -m cli.review repo --repo . --base main --head feature/my-branch
```

---

## ⚙️ GitHub Actions (Automatic Self-Review)

Add your `OPENAI_API_KEY` to your repository's **Secrets** (Settings → Secrets → Actions), then the included `.github/workflows/code-review.yml` will automatically run a review on every Pull Request.

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

---

## 🔧 Configuration Reference

| Variable | Description | Default |
|---|---|---|
| `OPENAI_API_KEY` | Your OpenAI API key | *(required)* |
| `OPENAI_MODEL` | Model to use | `gpt-4o` |
| `GITHUB_TOKEN` | GitHub Personal Access Token | *(required for GitHub)* |
| `GITHUB_WEBHOOK_SECRET` | GitHub webhook secret | *(recommended)* |
| `GITLAB_TOKEN` | GitLab Personal Access Token | *(required for GitLab)* |
| `GITLAB_WEBHOOK_SECRET` | GitLab webhook secret token | *(recommended)* |
| `BITBUCKET_USERNAME` | Bitbucket username | *(required for Bitbucket)* |
| `BITBUCKET_APP_PASSWORD` | Bitbucket app password | *(required for Bitbucket)* |
| `MAX_DIFF_SIZE_KB` | Skip diffs larger than this | `500` |
| `LOG_LEVEL` | Logging level | `INFO` |

---

## 📄 License

MIT © [akhila2821](https://github.com/akhila2821)
