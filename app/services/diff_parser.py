"""
Unified diff parser.

Converts raw unified-diff text (as returned by GitHub/GitLab/Bitbucket APIs
or `git diff`) into structured FileDiff / DiffHunk objects.
"""

from __future__ import annotations

import re
from app.models import DiffHunk, FileDiff
from app.utils.logger import get_logger

log = get_logger(__name__)

# Regex patterns
_FILE_HEADER_RE = re.compile(
    r"^diff --git a/(?P<old>.+?) b/(?P<new>.+)$", re.MULTILINE
)
_OLD_FILE_RE = re.compile(r"^--- (?:a/)?(.+)$", re.MULTILINE)
_NEW_FILE_RE = re.compile(r"^\+\+\+ (?:b/)?(.+)$", re.MULTILINE)
_HUNK_HEADER_RE = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.MULTILINE
)
_STATUS_ADDED = re.compile(r"^new file mode", re.MULTILINE)
_STATUS_DELETED = re.compile(r"^deleted file mode", re.MULTILINE)
_STATUS_RENAMED = re.compile(r"^similarity index", re.MULTILINE)


def parse_diff(raw_diff: str) -> list[FileDiff]:
    """
    Parse a full unified diff string into a list of FileDiff objects.

    Args:
        raw_diff: Raw unified diff text.

    Returns:
        List of FileDiff, one per changed file.
    """
    if not raw_diff or not raw_diff.strip():
        return []

    # Split the diff at each "diff --git" boundary
    segments = re.split(r"(?=^diff --git )", raw_diff, flags=re.MULTILINE)
    file_diffs: list[FileDiff] = []

    for segment in segments:
        if not segment.strip():
            continue
        try:
            fd = _parse_file_segment(segment)
            if fd:
                file_diffs.append(fd)
        except Exception as exc:
            log.warning("Failed to parse diff segment: %s", exc)

    log.debug("Parsed %d file diffs from raw diff (%d bytes)", len(file_diffs), len(raw_diff))
    return file_diffs


def _parse_file_segment(segment: str) -> FileDiff | None:
    """Parse a single file's diff segment."""
    header_match = _FILE_HEADER_RE.search(segment)
    if not header_match:
        return None

    old_path = header_match.group("old")
    new_path = header_match.group("new")

    # Determine status
    if _STATUS_ADDED.search(segment):
        status = "added"
    elif _STATUS_DELETED.search(segment):
        status = "deleted"
    elif _STATUS_RENAMED.search(segment):
        status = "renamed"
    else:
        status = "modified"

    # Parse hunks
    hunks = _parse_hunks(segment)

    return FileDiff(
        filename=new_path,
        old_filename=old_path if old_path != new_path else None,
        status=status,
        hunks=hunks,
        raw_diff=segment,
    )


def _parse_hunks(segment: str) -> list[DiffHunk]:
    """Extract all diff hunks from a file segment."""
    hunk_positions = [m.start() for m in _HUNK_HEADER_RE.finditer(segment)]
    if not hunk_positions:
        return []

    hunks: list[DiffHunk] = []
    for i, pos in enumerate(hunk_positions):
        end = hunk_positions[i + 1] if i + 1 < len(hunk_positions) else len(segment)
        hunk_text = segment[pos:end]
        hunk = _parse_single_hunk(hunk_text)
        if hunk:
            hunks.append(hunk)

    return hunks


def _parse_single_hunk(hunk_text: str) -> DiffHunk | None:
    """Parse one hunk block."""
    header_match = _HUNK_HEADER_RE.match(hunk_text)
    if not header_match:
        return None

    old_start = int(header_match.group(1))
    old_count = int(header_match.group(2) or 1)
    new_start = int(header_match.group(3))
    new_count = int(header_match.group(4) or 1)

    # Collect the diff lines (skip the @@ header line)
    body = hunk_text[header_match.end():]
    lines = body.splitlines()

    return DiffHunk(
        old_start=old_start,
        old_count=old_count,
        new_start=new_start,
        new_count=new_count,
        lines=lines,
    )


def diff_to_text(file_diffs: list[FileDiff], max_kb: int = 500) -> str:
    """
    Flatten parsed diffs back into a single string for the LLM prompt.
    Truncates if the total exceeds *max_kb* kilobytes.
    """
    parts: list[str] = []
    total_bytes = 0
    limit = max_kb * 1024

    for fd in file_diffs:
        chunk = f"### File: {fd.filename} ({fd.status})\n{fd.raw_diff}\n"
        encoded = chunk.encode()
        if total_bytes + len(encoded) > limit:
            parts.append(
                f"\n⚠️  Diff truncated at {max_kb} KB. "
                "Remaining files skipped to fit context window."
            )
            break
        parts.append(chunk)
        total_bytes += len(encoded)

    return "\n".join(parts)
