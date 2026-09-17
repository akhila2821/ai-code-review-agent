"""
Markdown report generator.

Converts a ReviewResult into a rich, readable Markdown comment
suitable for posting on GitHub PRs, GitLab MRs, or Bitbucket PRs.
"""

from __future__ import annotations

from app.models import Finding, ReviewResult, Severity

# Severity → emoji mapping
_SEVERITY_EMOJI: dict[Severity, str] = {
    Severity.CRITICAL: "🔴",
    Severity.HIGH: "🟠",
    Severity.MEDIUM: "🟡",
    Severity.LOW: "🔵",
    Severity.INFO: "⚪",
}

_SCORE_EMOJI = {
    (90, 101): "🏆",
    (75, 90): "✅",
    (50, 75): "⚠️",
    (0, 50): "❌",
}


def _score_emoji(score: int) -> str:
    for (lo, hi), emoji in _SCORE_EMOJI.items():
        if lo <= score < hi:
            return emoji
    return "❓"


def _findings_table(findings: list[Finding]) -> str:
    if not findings:
        return "_No issues found_ ✨\n"

    rows = ["| Severity | File | Line | Issue | Suggestion |",
            "|---|---|---|---|---|"]
    for f in findings:
        sev = f"{_SEVERITY_EMOJI.get(f.severity, '')} {f.severity.value}"
        line = str(f.line) if f.line else "—"
        rows.append(f"| {sev} | `{f.file}` | {line} | {f.message} | {f.suggestion} |")
    return "\n".join(rows) + "\n"


def generate_report(result: ReviewResult, pr_title: str = "") -> str:
    """
    Render a full Markdown review report.

    Args:
        result: Parsed ReviewResult from the AI reviewer.
        pr_title: Optional PR title to include in the header.

    Returns:
        Markdown-formatted string ready to post as a PR comment.
    """
    title_line = f"**{pr_title}**" if pr_title else "this PR"
    score_icon = _score_emoji(result.score)

    sections: list[str] = [
        "## 🤖 AI Code Review Report",
        "",
        f"> Reviewing {title_line}",
        "",
        f"### {score_icon} Quality Score: **{result.score}/100**",
        "",
        f"**Summary:** {result.summary}",
        "",
        f"**Total findings:** {result.total_findings}  ",
        f"{'⚠️ **Critical issues detected — please address before merging.**' if result.has_critical_issues else ''}",
        "",
    ]

    # Praise section
    if result.praise:
        sections += [
            "### 🌟 What's done well",
            "",
            *[f"- {p}" for p in result.praise],
            "",
        ]

    # Bugs
    sections += [
        "### 🐛 Bugs",
        "",
        _findings_table(result.bugs),
    ]

    # Security
    sections += [
        "### 🔒 Security",
        "",
        _findings_table(result.security),
    ]

    # Style / Linting
    sections += [
        "### 🎨 Style & Linting",
        "",
        _findings_table(result.style),
    ]

    # Improvements
    sections += [
        "### 💡 Improvements & Refactoring",
        "",
        _findings_table(result.improvements),
    ]

    # Test gaps
    sections += [
        "### 🧪 Test Coverage Gaps",
        "",
        _findings_table(result.test_gaps),
    ]

    sections += [
        "---",
        "_Powered by [AI Code Review Agent](https://github.com/akhila2821/ai-code-review-agent) · GPT-4o_",
    ]

    return "\n".join(sections)


def generate_inline_comment(finding: Finding) -> str:
    """
    Generate a short inline comment for a single finding.
    Used when posting per-line comments on a PR diff.
    """
    icon = _SEVERITY_EMOJI.get(finding.severity, "")
    lines = [
        f"{icon} **[{finding.severity.value.upper()}]** {finding.message}",
    ]
    if finding.suggestion:
        lines.append(f"\n> 💡 **Suggestion:** {finding.suggestion}")
    return "\n".join(lines)
