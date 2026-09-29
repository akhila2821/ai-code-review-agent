# CodeGuard AI

AI Code Review & Vulnerability Detection Agent — powered by OpenAI GPT-4o.

## Features
- Source code input (JavaScript, Python, Java, TypeScript, SQL, PHP, Go)
- AI-powered bug detection via GPT-4o
- Security vulnerability detection (SQLi, XSS, command injection, hardcoded secrets, etc.)
- Code smell & maintainability detection
- Severity classification (Critical / High / Medium / Low)
- Explanation of findings with line numbers
- Concrete fix suggestions
- Animated security score (0–100)
- Filterable & sortable issue list
- Export report to clipboard

## Local Development

### 1. Clone & install
```bash
git clone <your-repo-url>
cd codeathon
npm install
```

### 2. Configure environment
```bash
cp .env.example .env
# Open .env and set your OPENAI_API_KEY
```

### 3. Start the server
```bash
npm start
# → http://localhost:3001
```

> **Alternative:** You can also enter your API key directly in the app via the 🔑 button — no restart needed.

## Deploying to Render

1. Push your code to GitHub (`.env` and `node_modules` are excluded via `.gitignore`)
2. Create a new **Web Service** on [render.com](https://render.com)
3. Connect your GitHub repo
4. Set **Build Command**: `npm install`
5. Set **Start Command**: `npm start`
6. Add the following **Environment Variables** in the Render dashboard:

| Variable | Value |
|---|---|
| `OPENAI_API_KEY` | Your real `sk-...` key from platform.openai.com |
| `NODE_ENV` | `production` |
| `ALLOWED_ORIGIN` | Your Render URL e.g. `https://codeguard-ai.onrender.com` |

> **Note:** `PORT` is set automatically by Render — do not set it manually.

## Security Notes
- `.env` is listed in `.gitignore` — your API key is never committed to GitHub
- All analysis runs server-side; user code is only forwarded to OpenAI and never stored
- CORS is restricted to `ALLOWED_ORIGIN` in production
