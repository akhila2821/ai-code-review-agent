"""
GPT-4o prompt templates for every review category.

Each template is a function that returns the messages list expected by
the OpenAI chat-completions API.
"""

from typing import Any

# ──────────────────────────────────────────────────────────────────────────────
# System prompt — sets the persona and output contract
# ──────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert software engineer performing a thorough code review.
Your goal is to produce actionable, concise, and developer-friendly feedback.

You MUST respond with a valid JSON object that has EXACTLY these keys:
{
  "summary": "...",           // 2-4 sentence overall assessment
  "score": 0-100,             // quality score (100 = perfect)
  "bugs": [...],              // list of bug findings
  "security": [...],          // list of security findings
  "style": [...],             // list of style / linting findings
  "improvements": [...],      // refactoring / design suggestions
  "test_gaps": [...],         // missing tests or untested paths
  "praise": [...]             // 1-3 things done well (keep morale high!)
}

Each finding in those arrays must be an object:
{
  "file": "path/to/file.py",
  "line": 42,                 // best-effort line number from the diff
  "severity": "critical|high|medium|low|info",
  "message": "...",           // what the issue is
  "suggestion": "..."         // concrete fix or improvement
}

Rules:
- Only comment on code that appears in the diff (changed lines).
- Be precise — cite file names and line numbers when possible.
- Do NOT invent issues that are not present in the diff.
- Be respectful and constructive — this is feedback for a human.
- If a category has no findings, return an empty array [].
"""


def build_review_messages(
    diff: str,
    pr_title: str = "",
    pr_description: str = "",
    extra_context: str = "",
) -> list[dict[str, Any]]:
    """
    Construct the messages payload for the GPT-4o chat API.

    Args:
        diff: Unified diff text to review.
        pr_title: Optional PR/MR title for context.
        pr_description: Optional PR/MR body for context.
        extra_context: Any additional context (repo language, guidelines, etc.).

    Returns:
        List of message dicts for openai.chat.completions.create(messages=...).
    """
    user_parts: list[str] = []

    if pr_title:
        user_parts.append(f"**PR Title:** {pr_title}")
    if pr_description:
        user_parts.append(f"**PR Description:**\n{pr_description}")
    if extra_context:
        user_parts.append(f"**Additional Context:**\n{extra_context}")

    user_parts.append(
        f"**Diff to review:**\n```diff\n{diff}\n```\n\n"
        "Please review the above diff and return your findings as the JSON object "
        "described in the system prompt."
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]
