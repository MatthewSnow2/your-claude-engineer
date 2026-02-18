"""
Compound Learning System
========================

Persists codebase learnings across sessions via .codebase_learnings.json.
Used by the code review agent to apply past learnings and record new ones,
and by the coding agent to understand codebase patterns before implementation.
"""

import json
from pathlib import Path
from typing import Any


# Default structure for new projects
DEFAULT_LEARNINGS: dict[str, Any] = {
    "codebase_patterns": {
        "framework": "",
        "styling": "",
        "state_management": "",
        "file_structure": "",
    },
    "common_mistakes": [],
    "effective_patterns": [],
    "review_findings": [],
}

LEARNINGS_FILENAME = ".codebase_learnings.json"


def load_learnings(project_dir: Path) -> dict[str, Any]:
    """Load .codebase_learnings.json from project dir.

    Returns existing learnings or a default empty structure if file doesn't exist.

    Args:
        project_dir: Path to the project directory

    Returns:
        Dict with codebase_patterns, common_mistakes, effective_patterns, review_findings
    """
    learnings_file = project_dir / LEARNINGS_FILENAME
    if not learnings_file.exists():
        return json.loads(json.dumps(DEFAULT_LEARNINGS))  # Deep copy

    try:
        with open(learnings_file) as f:
            data = json.load(f)
        # Ensure all expected keys exist (forward compatibility)
        for key, default_value in DEFAULT_LEARNINGS.items():
            if key not in data:
                data[key] = (
                    json.loads(json.dumps(default_value))
                    if isinstance(default_value, (dict, list))
                    else default_value
                )
        return data
    except (json.JSONDecodeError, IOError):
        return json.loads(json.dumps(DEFAULT_LEARNINGS))


def save_learnings(project_dir: Path, learnings: dict[str, Any]) -> None:
    """Save updated learnings to project dir.

    Args:
        project_dir: Path to the project directory
        learnings: Dict with codebase learnings to persist
    """
    learnings_file = project_dir / LEARNINGS_FILENAME
    project_dir.mkdir(parents=True, exist_ok=True)
    with open(learnings_file, "w") as f:
        json.dump(learnings, f, indent=2)


def format_learnings_for_prompt(learnings: dict[str, Any]) -> str:
    """Format learnings as a markdown section to append to agent prompts.

    Args:
        learnings: Dict loaded from .codebase_learnings.json

    Returns:
        Markdown-formatted string with codebase context for agent prompts.
        Returns empty string if no meaningful learnings exist.
    """
    sections: list[str] = []

    # Codebase patterns
    patterns = learnings.get("codebase_patterns", {})
    pattern_lines: list[str] = []
    for key, value in patterns.items():
        if value:
            pattern_lines.append(f"- **{key}**: {value}")
    if pattern_lines:
        sections.append("### Codebase Patterns\n" + "\n".join(pattern_lines))

    # Common mistakes to avoid
    mistakes = learnings.get("common_mistakes", [])
    if mistakes:
        mistake_lines = [
            f"- {m.get('issue', 'Unknown issue')} → {m.get('fix', 'No fix recorded')}"
            for m in mistakes[-5:]  # Last 5 mistakes (most recent)
        ]
        sections.append(
            "### Common Mistakes to Avoid\n" + "\n".join(mistake_lines)
        )

    # Effective patterns
    effective = learnings.get("effective_patterns", [])
    if effective:
        effective_lines = [
            f"- {p.get('pattern', 'Unknown pattern')} (confidence: {p.get('confidence', 'unknown')})"
            for p in effective[-5:]  # Last 5 patterns
        ]
        sections.append(
            "### Effective Patterns\n" + "\n".join(effective_lines)
        )

    # Recent review findings
    findings = learnings.get("review_findings", [])
    if findings:
        finding_lines = [
            f"- [{f.get('type', 'general')}] {f.get('finding', 'Unknown finding')}"
            for f in findings[-3:]  # Last 3 findings
        ]
        sections.append(
            "### Recent Review Findings\n" + "\n".join(finding_lines)
        )

    if not sections:
        return ""

    return "## CODEBASE CONTEXT (from past sessions)\n\n" + "\n\n".join(sections)
