require('dotenv').config();
const express = require('express');
const cors = require('cors');
const OpenAI = require('openai');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3001;
const isProduction = process.env.NODE_ENV === 'production';

// CORS: restrict to configured origin in production; allow all in local dev
const corsOptions = {
  origin: process.env.ALLOWED_ORIGIN || (isProduction ? false : '*'),
  methods: ['GET', 'POST'],
  allowedHeaders: ['Content-Type', 'x-api-key'],
};
app.use(cors(corsOptions));
app.use(express.json({ limit: '512kb' }));
app.use(express.static(path.join(__dirname)));


const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

// ── Health check ─────────────────────────────────────────────────────────────
app.get('/api/health', (_req, res) => res.json({ status: 'ok' }));

// ── AI Analysis endpoint ──────────────────────────────────────────────────────
app.post('/api/analyse', async (req, res) => {
  const { code, language } = req.body;

  if (!code || typeof code !== 'string' || code.trim().length === 0) {
    return res.status(400).json({ error: 'No code provided.' });
  }
  // Allow per-request key override from the UI
  const requestKey = req.headers['x-api-key'];
  const activeKey = requestKey || process.env.OPENAI_API_KEY;

  if (!activeKey || activeKey === 'your_openai_api_key_here') {
    return res.status(500).json({ error: 'OpenAI API key not configured. Click the 🔑 API Key button in the app, or set OPENAI_API_KEY in your .env file.' });
  }

  const systemPrompt = `You are CodeGuard AI, an expert security-focused code review engine. 
Analyse the provided source code for ALL of the following categories, be thorough:
1. Security vulnerabilities (SQL injection, XSS, command injection, hardcoded secrets, unsafe deserialization, path traversal, CSRF, insecure cryptography, etc.)
2. Bugs (logic errors, null pointer risks, off-by-one errors, resource leaks, race conditions, unhandled exceptions, always-true/false conditions, etc.)
3. Code smells (long functions, deep nesting, magic numbers, dead code, duplicated code, poor naming, missing error handling, etc.)
4. Maintainability issues (overly complex methods, missing documentation for public API, God classes, tight coupling, etc.)

You MUST respond ONLY with a valid JSON object in exactly this schema (no markdown fences, no explanation outside JSON):

{
  "securityScore": <integer 0-100>,
  "summary": "<one sentence overall assessment>",
  "issues": [
    {
      "id": "<unique short id e.g. SEC-001>",
      "title": "<short descriptive title>",
      "category": "<Security|Bug|Code Smell|Maintainability>",
      "severity": "<Critical|High|Medium|Low>",
      "line": <line number as integer, 0 if not applicable>,
      "explanation": "<clear explanation of why this is a problem, max 3 sentences>",
      "fix": "<concrete actionable fix suggestion, max 3 sentences>",
      "codeSnippet": "<the problematic code snippet (max 80 chars) or empty string>"
    }
  ]
}

Rules:
- securityScore starts at 100, deduct: Critical=25, High=15, Medium=8, Low=3 per issue (min 0)
- Return at least the issues you find; if code is clean return an empty issues array
- Be specific about line numbers when possible
- Do NOT invent issues that don't exist in the code
- Language context: ${language || 'auto-detect'}`;

  try {
    const completion = await new OpenAI({ apiKey: activeKey }).chat.completions.create({
      model: 'gpt-4o',
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: `Analyse this ${language || ''} code:\n\n\`\`\`${language || ''}\n${code}\n\`\`\`` }
      ],
      temperature: 0.2,
      max_tokens: 4096,
      response_format: { type: 'json_object' }
    });

    const raw = completion.choices[0].message.content;
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch {
      return res.status(500).json({ error: 'AI returned invalid JSON. Please try again.' });
    }

    // Normalise / ensure required fields
    if (!Array.isArray(parsed.issues)) parsed.issues = [];
    parsed.issues = parsed.issues.map((issue, i) => ({
      id: issue.id || `ISS-${String(i + 1).padStart(3, '0')}`,
      title: issue.title || 'Unknown issue',
      category: issue.category || 'Code Smell',
      severity: issue.severity || 'Low',
      line: typeof issue.line === 'number' ? issue.line : 0,
      explanation: issue.explanation || '',
      fix: issue.fix || '',
      codeSnippet: issue.codeSnippet || ''
    }));

    if (typeof parsed.securityScore !== 'number') {
      let score = 100;
      parsed.issues.forEach(x => {
        score -= x.severity === 'Critical' ? 25 : x.severity === 'High' ? 15 : x.severity === 'Medium' ? 8 : 3;
      });
      parsed.securityScore = Math.max(0, score);
    }

    res.json(parsed);
  } catch (err) {
    const msg = err?.error?.message || err?.message || 'Unknown error from OpenAI API';
    console.error('OpenAI error:', msg);
    res.status(502).json({ error: msg });
  }
});

app.listen(PORT, () => {
  console.log(`\n🛡️  CodeGuard AI backend running → http://localhost:${PORT}`);
  console.log(`   Open http://localhost:${PORT} in your browser\n`);
});
