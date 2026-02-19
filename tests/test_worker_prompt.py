"""Tests for the worker task prompt template."""

import re
from pathlib import Path

import pytest


PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class TestWorkerPromptTemplate:
    def test_template_exists(self) -> None:
        assert (PROMPTS_DIR / "worker_task.md").exists()

    def test_template_has_all_placeholders(self) -> None:
        template = (PROMPTS_DIR / "worker_task.md").read_text()
        required_placeholders = [
            "{issue_id}",
            "{issue_title}",
            "{issue_category}",
            "{issue_priority}",
            "{worktree_dir}",
            "{branch}",
            "{project_dir}",
            "{codebase_learnings}",
        ]
        for placeholder in required_placeholders:
            assert placeholder in template, f"Missing placeholder: {placeholder}"

    def test_template_formats_cleanly(self) -> None:
        template = (PROMPTS_DIR / "worker_task.md").read_text()
        result = template.format(
            issue_id="M2A-30",
            issue_title="Implement shared state",
            issue_category="feature",
            issue_priority="Medium",
            worktree_dir="/tmp/.workers/w0",
            branch="parallel/M2A-30",
            project_dir="/tmp/project",
            codebase_learnings="",
        )
        # Verify no unformatted placeholders remain
        remaining = re.findall(r"\{[a-z_]+\}", result)
        assert remaining == [], f"Unformatted placeholders: {remaining}"

    def test_template_preserves_json_braces(self) -> None:
        """Double braces {{ }} in the template should become single { } after format."""
        template = (PROMPTS_DIR / "worker_task.md").read_text()
        result = template.format(
            issue_id="T-1",
            issue_title="Test",
            issue_category="backend",
            issue_priority="High",
            worktree_dir="/tmp/w0",
            branch="parallel/T-1",
            project_dir="/tmp/project",
            codebase_learnings="",
        )
        # The formatted result should contain valid JSON-like blocks
        assert '"issue_id": "T-1"' in result
        assert '"status": "success"' in result
        assert '"status": "error"' in result

    def test_template_mentions_mandatory_gates(self) -> None:
        template = (PROMPTS_DIR / "worker_task.md").read_text()
        assert "Code Review (MANDATORY)" in template
        assert "QA Verification (MANDATORY)" in template

    def test_template_prohibits_linear_and_slack(self) -> None:
        template = (PROMPTS_DIR / "worker_task.md").read_text()
        assert "Do NOT query Linear" in template
        assert "Do NOT send Slack" in template
        assert "Do NOT push to remote" in template
