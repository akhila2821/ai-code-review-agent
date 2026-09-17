"""
Local CLI for running AI code reviews without a webhook server.

Usage examples:
    python -m cli.review --file path/to/myfile.py
    python -m cli.review --diff changes.patch
    python -m cli.review --repo . --base main --head feature/my-branch
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from app.services.ai_reviewer import review_diff
from app.services.diff_parser import diff_to_text, parse_diff
from app.services.report_generator import generate_report
from app.utils.logger import configure_logging

configure_logging()
console = Console()


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _file_to_diff(filepath: str) -> str:
    """Generate a minimal unified diff for a single file (entire content as '+' lines)."""
    path = Path(filepath)
    if not path.exists():
        raise click.BadParameter(f"File not found: {filepath}")

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    diff_lines = [f"+{line}" for line in lines]
    hunk_header = f"@@ -0,0 +1,{len(lines)} @@"
    return (
        f"diff --git a/{path.name} b/{path.name}\n"
        f"new file mode 100644\n"
        f"--- /dev/null\n"
        f"+++ b/{path.name}\n"
        f"{hunk_header}\n"
        + "\n".join(diff_lines)
    )


def _git_diff(repo: str, base: str, head: str) -> str:
    """Run git diff between two refs and return the unified diff text."""
    result = subprocess.run(
        ["git", "diff", f"{base}...{head}"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _print_findings_table(title: str, findings, console: Console) -> None:
    if not findings:
        return
    table = Table(title=title, show_lines=True, style="bold")
    table.add_column("Severity", style="bold", width=10)
    table.add_column("File", style="cyan")
    table.add_column("Line", justify="right", width=6)
    table.add_column("Issue")
    table.add_column("Suggestion", style="italic")

    severity_colors = {
        "critical": "red",
        "high": "orange3",
        "medium": "yellow",
        "low": "blue",
        "info": "white",
    }
    for f in findings:
        color = severity_colors.get(f.severity.value, "white")
        table.add_row(
            f"[{color}]{f.severity.value.upper()}[/{color}]",
            f.file,
            str(f.line) if f.line else "—",
            f.message,
            f.suggestion,
        )
    console.print(table)


async def _async_review(diff_text: str, title: str) -> None:
    """Run the review and print results to the terminal."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Reviewing with GPT-4o…", total=None)
        result = await review_diff(diff_text=diff_text, pr_title=title)

    # Header panel
    score_color = (
        "green" if result.score >= 75
        else "yellow" if result.score >= 50
        else "red"
    )
    console.print(
        Panel(
            f"[bold {score_color}]Quality Score: {result.score}/100[/bold {score_color}]\n\n"
            f"{result.summary}",
            title="🤖 AI Code Review",
            border_style=score_color,
        )
    )

    if result.praise:
        console.print("\n[bold green]🌟 What's done well:[/bold green]")
        for p in result.praise:
            console.print(f"  ✓ {p}")

    _print_findings_table("🐛 Bugs", result.bugs, console)
    _print_findings_table("🔒 Security", result.security, console)
    _print_findings_table("🎨 Style & Linting", result.style, console)
    _print_findings_table("💡 Improvements", result.improvements, console)
    _print_findings_table("🧪 Test Coverage Gaps", result.test_gaps, console)

    console.print(f"\n[dim]Total findings: {result.total_findings}[/dim]")

    # Also dump full markdown report
    report = generate_report(result, pr_title=title)
    if click.confirm("\nSave full Markdown report to file?", default=False):
        out_path = Path("review_report.md")
        out_path.write_text(report, encoding="utf-8")
        console.print(f"[green]Report saved to {out_path.resolve()}[/green]")


# ──────────────────────────────────────────────────────────────────────────────
# CLI commands
# ──────────────────────────────────────────────────────────────────────────────

@click.group()
def cli() -> None:
    """🤖 AI Code Review Agent — local CLI."""


@cli.command("file")
@click.option("--file", "-f", required=True, help="Path to the file to review.")
@click.option("--title", "-t", default="Local File Review", help="Review title.")
def review_file(file: str, title: str) -> None:
    """Review a single file."""
    try:
        raw_diff = _file_to_diff(file)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)

    file_diffs = parse_diff(raw_diff)
    diff_text = diff_to_text(file_diffs)
    asyncio.run(_async_review(diff_text, title))


@cli.command("diff")
@click.option("--diff", "-d", required=True, help="Path to a .patch / unified diff file.")
@click.option("--title", "-t", default="Diff Review", help="Review title.")
def review_diff_file(diff: str, title: str) -> None:
    """Review a unified diff / patch file."""
    path = Path(diff)
    if not path.exists():
        console.print(f"[red]Diff file not found:[/red] {diff}")
        sys.exit(1)

    raw_diff = path.read_text(encoding="utf-8")
    file_diffs = parse_diff(raw_diff)
    diff_text = diff_to_text(file_diffs)
    asyncio.run(_async_review(diff_text, title))


@cli.command("repo")
@click.option("--repo", "-r", default=".", help="Path to the git repository.")
@click.option("--base", "-b", default="main", help="Base branch or commit.")
@click.option("--head", "-H", default="HEAD", help="Head branch or commit.")
@click.option("--title", "-t", default="", help="Optional review title.")
def review_repo(repo: str, base: str, head: str, title: str) -> None:
    """Review the diff between two git refs."""
    try:
        raw_diff = _git_diff(repo, base, head)
    except subprocess.CalledProcessError as exc:
        console.print(f"[red]git diff failed:[/red] {exc.stderr}")
        sys.exit(1)

    if not raw_diff.strip():
        console.print("[yellow]No differences found between the two refs.[/yellow]")
        return

    label = title or f"{base}...{head}"
    file_diffs = parse_diff(raw_diff)
    diff_text = diff_to_text(file_diffs)
    asyncio.run(_async_review(diff_text, label))


if __name__ == "__main__":
    cli()
