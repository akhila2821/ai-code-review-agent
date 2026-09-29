/* ─────────────────────────────────────────────────
   CodeGuard AI — Frontend Application Logic
   Connects to Express/OpenAI backend at /api/analyse
───────────────────────────────────────────────── */

// API_BASE auto-detects environment:
// • Production (Render): same origin the page is served from (no hardcoded URL)
// • Local dev: falls back to localhost:3001
const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  ? 'http://localhost:3001'
  : window.location.origin;


// ── DOM refs ────────────────────────────────────────────
const codeInput     = document.getElementById('codeInput');
const language      = document.getElementById('language');
const sampleBtn     = document.getElementById('sampleBtn');
const clearBtn      = document.getElementById('clearBtn');
const scanBtn       = document.getElementById('scanBtn');
const scanBtnText   = document.getElementById('scanBtnText');
const results       = document.getElementById('results');
const emptyState    = document.getElementById('emptyState');
const loadingState  = document.getElementById('loadingState');
const issuesList    = document.getElementById('issuesList');
const lineNumbers   = document.getElementById('lineNumbers');
const lineCount     = document.getElementById('lineCount');
const apiStatus     = document.getElementById('apiStatus');
const statusDot     = apiStatus.querySelector('.dot');
const statusText    = document.getElementById('statusText');
const apiKeyBtn     = document.getElementById('apiKeyBtn');
const keyModal      = document.getElementById('keyModal');
const keyInput      = document.getElementById('keyInput');
const keySaveBtn    = document.getElementById('keySaveBtn');
const keyModalClose = document.getElementById('keyModalClose');
const keyModalCancel= document.getElementById('keyModalCancel');
const keyTestResult = document.getElementById('keyTestResult');
const reanalyseBtn  = document.getElementById('reanalyseBtn');
const exportBtn     = document.getElementById('exportBtn');
const loadingBar    = document.getElementById('loadingBar');
const loadingMsg    = document.getElementById('loadingMsg');

// ── State ────────────────────────────────────────────────
let allFindings = [];
let currentFilter = 'all';
let currentSort   = 'severity';
let sessionApiKey = localStorage.getItem('codeguard_key') || '';

// ── Sample code ──────────────────────────────────────────
const samples = {
  javascript: `function login(username, password) {
  const query = "SELECT * FROM users WHERE name = '" + username + "'";
  const secret = "admin123";
  document.innerHTML = "<h1>Welcome " + username + "</h1>";
  eval(password);
  console.log("Password:", password);
  return query;
}

function getUser(id) {
  return fetch("/api/users/" + id).then(r => r.json());
}

// TODO: add rate limiting
function processData(items) {
  var results = [];
  for(var i = 0; i <= items.length; i++) {
    results.push(items[i].value * 2);
  }
  return results;
}`,

  python: `import subprocess
import pickle

password = "admin123"

def run_command(user_input):
    result = subprocess.run("ping " + user_input, shell=True, capture_output=True)
    return result.stdout

def load_data(data):
    return pickle.loads(data)

def find_user(db, username):
    query = "SELECT * FROM users WHERE name = '" + username + "'"
    return db.execute(query)

try:
    connect()
except:
    pass`,

  java: `public class UserService {
    private String password = "admin123";

    public void execute(String input) throws Exception {
        Runtime.getRuntime().exec("cmd /c " + input);
        System.out.println("Password: " + password);
    }

    public void find(String name) {
        String sql = "SELECT * FROM users WHERE name = '" + name + "'";
        System.out.println(sql);
    }
}`,

  // NOTE: The value below is a FAKE placeholder — intentional vulnerable sample
  // code so GPT-4o can detect "hardcoded secret" as a vulnerability. NOT a real key.
  typescript: `import axios from 'axios';

const API_KEY = "sk-prod-abc123secretkey"; // ← intentional hardcoded-secret demo

async function fetchUser(userId: string) {
  const url = \`http://api.example.com/users/\${userId}\`;
  const res = await axios.get(url, {
    headers: { Authorization: \`Bearer \${API_KEY}\` }
  });
  document.querySelector('#content')!.innerHTML = res.data.bio;
  return res.data;
}

function saveToken(token: string) {
  localStorage.setItem('auth_token', token);
  console.log('Token saved:', token);
}`,

  sql: `SELECT * FROM users WHERE username = 'admin' AND password = 'password123';
SELECT * FROM users WHERE id = 1 OR 1=1;
SELECT * FROM accounts WHERE balance > 0; -- no LIMIT clause
DROP TABLE IF EXISTS temp_users;`,

  php: `<?php
$password = "admin123";
$conn = new mysqli($host, $user, $password, $db);

$name = $_GET['name'];
$query = "SELECT * FROM users WHERE name = '$name'";
$result = $conn->query($query);

echo "<div>" . $_GET['message'] . "</div>";
eval($_POST['code']);
?>`,

  go: `package main

import (
  "fmt"
  "os/exec"
  "database/sql"
)

const apiSecret = "super-secret-key-12345"

func runQuery(db *sql.DB, username string) {
  query := "SELECT * FROM users WHERE name = '" + username + "'"
  db.Query(query)
}

func runCmd(input string) {
  cmd := exec.Command("bash", "-c", input)
  out, _ := cmd.Output()
  fmt.Println(string(out))
}`
};

// ── Health check ─────────────────────────────────────────
async function checkHealth() {
  try {
    const r = await fetch(`${API_BASE}/api/health`, { signal: AbortSignal.timeout(4000) });
    if (r.ok) {
      setStatus('online', '🛡️ Backend Connected');
    } else {
      setStatus('offline', 'Backend Error');
    }
  } catch {
    setStatus('offline', 'Backend Offline');
  }
}

function setStatus(state, text) {
  statusDot.className = `dot ${state}`;
  statusText.textContent = text;
}

// ── Line numbers sync ─────────────────────────────────────
function updateEditor() {
  const val = codeInput.value;
  const lines = val ? val.split('\n') : [];
  const n = lines.length;
  lineNumbers.textContent = Array.from({ length: Math.max(n, 1) }, (_, i) => i + 1).join('\n');
  lineCount.textContent = `${n} lines · ${val.length} chars`;
}
codeInput.addEventListener('input', updateEditor);
codeInput.addEventListener('scroll', () => { lineNumbers.scrollTop = codeInput.scrollTop; });

language.addEventListener('change', () => {
  if (!codeInput.value.trim()) {
    codeInput.value = samples[language.value] || '';
    updateEditor();
  }
});

sampleBtn.onclick = () => {
  codeInput.value = samples[language.value] || samples.javascript;
  updateEditor();
};

clearBtn.onclick = () => {
  codeInput.value = '';
  updateEditor();
  showEmpty();
};

// ── API Key modal ─────────────────────────────────────────
function openKeyModal() {
  keyInput.value = sessionApiKey;
  keyTestResult.className = 'key-test-result hidden';
  keyTestResult.textContent = '';
  keyModal.classList.remove('hidden');
  keyInput.focus();
}
function closeKeyModal() { keyModal.classList.add('hidden'); }

apiKeyBtn.onclick     = openKeyModal;
keyModalClose.onclick = closeKeyModal;
keyModalCancel.onclick= closeKeyModal;
keyModal.onclick = (e) => { if (e.target === keyModal) closeKeyModal(); };

keySaveBtn.onclick = async () => {
  const key = keyInput.value.trim();
  if (!key.startsWith('sk-')) {
    showKeyResult('error', '❌ Invalid key format. Must start with sk-');
    return;
  }
  keySaveBtn.textContent = 'Testing…';
  keySaveBtn.disabled = true;
  // We just save it — actual test happens on first analyse
  sessionApiKey = key;
  localStorage.setItem('codeguard_key', key);
  showKeyResult('success', '✅ Key saved. It will be used for your next analysis.');
  keySaveBtn.textContent = 'Save & Test';
  keySaveBtn.disabled = false;
  setTimeout(closeKeyModal, 1500);
};

function showKeyResult(type, msg) {
  keyTestResult.className = `key-test-result ${type}`;
  keyTestResult.textContent = msg;
  keyTestResult.classList.remove('hidden');
}

// ── Loading animation ─────────────────────────────────────
const loadingMessages = [
  'Scanning for security vulnerabilities…',
  'Checking for SQL injection & XSS…',
  'Analysing command injection risks…',
  'Detecting hardcoded secrets…',
  'Reviewing bug patterns…',
  'Assessing code quality & smells…',
  'Computing security score…',
  'Preparing detailed report…',
];
let loadingInterval = null;
let loadingProgress = 0;

function startLoading() {
  loadingState.classList.remove('hidden');
  results.classList.add('hidden');
  emptyState.classList.add('hidden');
  loadingProgress = 0;
  loadingBar.style.width = '0%';
  let msgIdx = 0;
  loadingMsg.textContent = loadingMessages[0];

  loadingInterval = setInterval(() => {
    msgIdx = (msgIdx + 1) % loadingMessages.length;
    loadingMsg.textContent = loadingMessages[msgIdx];
    loadingProgress = Math.min(loadingProgress + Math.random() * 12, 85);
    loadingBar.style.width = loadingProgress + '%';
  }, 1200);
}

function stopLoading() {
  clearInterval(loadingInterval);
  loadingBar.style.width = '100%';
  setTimeout(() => loadingState.classList.add('hidden'), 400);
}

// ── Main analyse ──────────────────────────────────────────
scanBtn.addEventListener('click', runAnalysis);
reanalyseBtn && (reanalyseBtn.onclick = runAnalysis);

async function runAnalysis() {
  const code = codeInput.value.trim();
  if (!code) { codeInput.focus(); showToast('Please paste some code to analyse.', 'error'); return; }

  scanBtn.disabled = true;
  scanBtnText.textContent = 'Analysing…';
  startLoading();

  try {
    const headers = { 'Content-Type': 'application/json' };
    if (sessionApiKey) headers['x-api-key'] = sessionApiKey;

    const res = await fetch(`${API_BASE}/api/analyse`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ code, language: language.value }),
      signal: AbortSignal.timeout(60000)
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || `Server error ${res.status}`);
    }

    allFindings = data.issues || [];
    renderResults(data);

  } catch (err) {
    stopLoading();
    emptyState.classList.remove('hidden');
    const msg = err.name === 'TimeoutError'
      ? 'Request timed out. The server may be slow — try again.'
      : err.message || 'Unknown error';
    showToast(`Analysis failed: ${msg}`, 'error');
  } finally {
    scanBtn.disabled = false;
    scanBtnText.textContent = 'Analyse with AI';
  }
}

// ── Render results ────────────────────────────────────────
function renderResults(data) {
  stopLoading();

  const issues  = data.issues || [];
  const score   = typeof data.securityScore === 'number' ? data.securityScore : 100;
  const summary = data.summary || '';

  // Score ring
  const circle = document.getElementById('scoreRingCircle');
  const circumference = 314;
  const offset = circumference - (score / 100) * circumference;
  circle.style.strokeDashoffset = offset;

  // Score colour
  const scoreStart = score >= 80 ? '#7c73ff' : score >= 50 ? '#f3bf57' : '#ff5367';
  const scoreEnd   = score >= 80 ? '#2eddb0' : score >= 50 ? '#ff865f' : '#ff5367';
  document.getElementById('scoreGradStart').setAttribute('stop-color', scoreStart);
  document.getElementById('scoreGradEnd').setAttribute('stop-color', scoreEnd);

  document.getElementById('scoreNum').textContent = score;
  document.getElementById('aiSummary').textContent = summary;

  const verdict = score >= 90 ? '🟢 Strong Security' : score >= 70 ? '🟡 Review Recommended' : score >= 50 ? '🟠 Needs Improvement' : '🔴 Critical Issues';
  document.getElementById('scoreVerdict').textContent = verdict;

  // Stats
  const high = issues.filter(x => x.severity === 'Critical' || x.severity === 'High').length;
  const smells = issues.filter(x => x.category === 'Code Smell' || x.category === 'Maintainability').length;
  document.getElementById('totalIssues').textContent  = issues.length;
  document.getElementById('criticalHigh').textContent = high;

  const grade = smells >= 4 || issues.length >= 8 ? 'C' : issues.length >= 4 ? 'B' : 'A';
  document.getElementById('qualityGrade').textContent = grade;
  document.getElementById('qualitySub').textContent =
    grade === 'A' ? 'Clean structure' : grade === 'B' ? 'Minor improvements' : 'Refactoring recommended';

  // Category breakdown
  const cats = { Security: 0, Bug: 0, 'Code Smell': 0, Maintainability: 0 };
  issues.forEach(x => { if (cats[x.category] !== undefined) cats[x.category]++; });
  const icons = { Security: '🔒', Bug: '🐞', 'Code Smell': '💡', Maintainability: '🏗️' };
  document.getElementById('breakdownRow').innerHTML = Object.entries(cats).map(([cat, cnt]) => `
    <div class="breakdown-chip">
      <span style="font-size:18px">${icons[cat]}</span>
      <div>
        <div class="breakdown-count">${cnt}</div>
        <div style="font-size:10px;color:var(--text-3)">${cat}</div>
      </div>
    </div>`).join('');

  // Reset filters
  currentFilter = 'all';
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.toggle('active', b.dataset.filter === 'all'));

  renderIssues();
  results.classList.remove('hidden');
  emptyState.classList.add('hidden');
  results.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── Issue rendering ───────────────────────────────────────
function renderIssues() {
  let filtered = currentFilter === 'all' ? [...allFindings] : allFindings.filter(x => x.category === currentFilter);

  const sevOrder = { Critical: 0, High: 1, Medium: 2, Low: 3 };
  if (currentSort === 'severity') filtered.sort((a, b) => (sevOrder[a.severity] ?? 4) - (sevOrder[b.severity] ?? 4));
  else if (currentSort === 'category') filtered.sort((a, b) => a.category.localeCompare(b.category));
  else if (currentSort === 'line') filtered.sort((a, b) => (a.line || 0) - (b.line || 0));

  document.getElementById('issueCount').textContent = `${filtered.length} issue${filtered.length !== 1 ? 's' : ''}`;

  if (!filtered.length) {
    issuesList.innerHTML = `<div class="empty-state">
      <div class="empty-icon">✅</div>
      <h3>No ${currentFilter === 'all' ? '' : currentFilter + ' '}issues found</h3>
      <p>Great — no matching findings detected by GPT-4o in this category.</p>
    </div>`;
    return;
  }

  const catIcon = { Security: '🔒', Bug: '🐞', 'Code Smell': '💡', Maintainability: '🏗️' };

  issuesList.innerHTML = filtered.map(issue => `
    <div class="issue-card">
      <div class="issue-icon-wrap">${catIcon[issue.category] || '⚠️'}</div>
      <div class="issue-body">
        <div class="issue-title">${escHtml(issue.title)}</div>
        <div class="issue-meta">
          <span class="pill pill-category">${escHtml(issue.category)}</span>
          ${issue.line ? `<span class="pill pill-line">Line ${issue.line}</span>` : ''}
          <span class="pill pill-id">${escHtml(issue.id)}</span>
        </div>
        <div class="issue-explanation">${escHtml(issue.explanation)}</div>
        ${issue.codeSnippet ? `<div class="code-snippet">${escHtml(issue.codeSnippet)}</div>` : ''}
        <div class="fix-block"><strong>💡 Fix:</strong> ${escHtml(issue.fix)}</div>
      </div>
      <span class="sev-badge sev-${issue.severity.toLowerCase()}">${escHtml(issue.severity)}</span>
    </div>`).join('');
}

function escHtml(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Filters ───────────────────────────────────────────────
document.getElementById('filterBar').addEventListener('click', e => {
  const btn = e.target.closest('.filter-btn');
  if (!btn) return;
  currentFilter = btn.dataset.filter;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.toggle('active', b === btn));
  renderIssues();
});

// ── Sort ──────────────────────────────────────────────────
['sortSeverity', 'sortCategory', 'sortLine'].forEach(id => {
  document.getElementById(id).addEventListener('click', function () {
    currentSort = { sortSeverity: 'severity', sortCategory: 'category', sortLine: 'line' }[id];
    document.querySelectorAll('.sort-btn').forEach(b => b.classList.toggle('active', b === this));
    renderIssues();
  });
});

// ── Export report ─────────────────────────────────────────
exportBtn && (exportBtn.onclick = () => {
  const lines = [`CodeGuard AI — Security Report`, `Language: ${language.value}`, `Score: ${document.getElementById('scoreNum').textContent}/100`, `Issues: ${allFindings.length}`, '', '─'.repeat(60), ''];
  allFindings.forEach(x => {
    lines.push(`[${x.severity}] ${x.title} (${x.category}) — Line ${x.line || '?'}`);
    lines.push(`ID: ${x.id}`);
    lines.push(`Issue: ${x.explanation}`);
    lines.push(`Fix: ${x.fix}`);
    if (x.codeSnippet) lines.push(`Snippet: ${x.codeSnippet}`);
    lines.push('');
  });
  navigator.clipboard.writeText(lines.join('\n'))
    .then(() => showToast('Report copied to clipboard!', 'success'))
    .catch(() => showToast('Could not copy — browser blocked clipboard access.', 'error'));
});

// ── Toast ─────────────────────────────────────────────────
function showToast(msg, type = 'error') {
  const t = document.createElement('div');
  t.className = `toast${type === 'success' ? ' success' : ''}`;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 4500);
}

function showEmpty() {
  results.classList.add('hidden');
  loadingState.classList.add('hidden');
  emptyState.classList.remove('hidden');
}

// ── Init ──────────────────────────────────────────────────
updateEditor();
checkHealth();
setInterval(checkHealth, 30000);
