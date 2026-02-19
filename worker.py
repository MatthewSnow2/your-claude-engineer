"""
Parallel Worker Process
=======================

A standalone script that runs the full pipeline for a single Linear issue
in an isolated git worktree. Invoked as a subprocess by the parallel coordinator.

Each worker gets its own:
- Git worktree (filesystem isolation)
- ClaudeSDKClient (own event loop, no anyio conflicts)
- MCP server instances (Playwright, Arcade)

Usage (as subprocess):
    python -m worker \
        --issue-id M2A-30 \
        --issue-title "Implement shared state" \
        --issue-category feature \
        --issue-priority Medium \
        --worktree-dir /path/.workers/w0 \
        --branch parallel/M2A-30 \
        --project-dir /path/to/project \
        --model claude-haiku-4-5-20251001 \
        --result-path /path/.workers/results/M2A-30.json
"""

import argparse
import asyncio
import json
import os
import sys
import time
import traceback
from pathlib import Path

from dotenv import load_dotenv

# Load shared credentials
load_dotenv(Path.home() / ".env.shared")
load_dotenv()


def parse_args() -> argparse.Namespace:
    """Parse worker subprocess arguments."""
    parser = argparse.ArgumentParser(description="Parallel worker for a single issue")
    parser.add_argument("--issue-id", required=True, help="Linear issue ID (e.g., M2A-30)")
    parser.add_argument("--issue-title", required=True, help="Issue title")
    parser.add_argument("--issue-category", required=True, help="Issue category")
    parser.add_argument("--issue-priority", default="Medium", help="Issue priority")
    parser.add_argument("--worktree-dir", required=True, type=Path, help="Git worktree directory")
    parser.add_argument("--branch", required=True, help="Git branch name")
    parser.add_argument("--project-dir", required=True, type=Path, help="Main project directory")
    parser.add_argument("--model", required=True, help="Full Claude model ID")
    parser.add_argument("--result-path", required=True, type=Path, help="Path to write result JSON")
    return parser.parse_args()


def build_worker_prompt(args: argparse.Namespace) -> str:
    """
    Build the worker task prompt with issue context substituted.

    Loads the worker_task.md template and fills in issue-specific values.
    """
    prompts_dir = Path(__file__).parent / "prompts"
    template_path = prompts_dir / "worker_task.md"
    template = template_path.read_text()

    # Load codebase learnings if available
    learnings_path = args.worktree_dir / ".codebase_learnings.json"
    codebase_learnings = ""
    if learnings_path.exists():
        try:
            with open(learnings_path) as f:
                learnings_data = json.load(f)
            if learnings_data:
                codebase_learnings = f"## Codebase Learnings\n```json\n{json.dumps(learnings_data, indent=2)}\n```"
        except (json.JSONDecodeError, IOError):
            pass

    return template.format(
        issue_id=args.issue_id,
        issue_title=args.issue_title,
        issue_category=args.issue_category,
        issue_priority=args.issue_priority,
        worktree_dir=args.worktree_dir,
        branch=args.branch,
        project_dir=args.project_dir,
        codebase_learnings=codebase_learnings,
    )


def create_worker_client(args: argparse.Namespace):
    """
    Create a ClaudeSDKClient configured for worker execution.

    Uses the worktree directory as cwd for file isolation.
    Reuses the same security settings and MCP config as the main client.
    """
    # Import here to avoid circular imports at module level
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, McpServerConfig
    from claude_agent_sdk.types import HookCallback, HookMatcher

    from arcade_config import (
        ALL_ARCADE_TOOLS,
        ARCADE_TOOLS_PERMISSION,
        get_arcade_mcp_config,
        validate_arcade_config,
    )
    from agents.definitions import AGENT_DEFINITIONS
    from client import (
        BUILTIN_TOOLS,
        PLAYWRIGHT_TOOLS,
        create_security_settings,
        load_orchestrator_prompt,
        write_security_settings,
    )
    from hooks import on_subagent_start, on_subagent_stop, validate_agent_output
    from security import bash_security_hook

    # Remove env vars that interfere with SDK subprocess
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.pop("CLAUDECODE", None)

    validate_arcade_config()
    arcade_config = get_arcade_mcp_config()

    # Write security settings to worktree directory
    security_settings = create_security_settings()
    settings_file = write_security_settings(args.worktree_dir, security_settings)

    # Use the orchestrator prompt as system prompt (worker task comes as user message)
    orchestrator_prompt = load_orchestrator_prompt()

    from typing import cast
    return ClaudeSDKClient(
        options=ClaudeAgentOptions(
            model=args.model,
            system_prompt=orchestrator_prompt,
            thinking={"type": "adaptive"},
            effort="high",
            enable_file_checkpointing=True,
            allowed_tools=[
                *BUILTIN_TOOLS,
                *PLAYWRIGHT_TOOLS,
                *ALL_ARCADE_TOOLS,
            ],
            mcp_servers=cast(
                dict[str, McpServerConfig],
                {
                    "playwright": {"command": "npx", "args": ["-y", "@playwright/mcp@latest"]},
                    "arcade": arcade_config,
                },
            ),
            hooks={
                "PreToolUse": [
                    HookMatcher(
                        matcher="Bash",
                        hooks=[cast(HookCallback, bash_security_hook)],
                    ),
                ],
                "PostToolUse": [
                    HookMatcher(
                        matcher="Task",
                        hooks=[cast(HookCallback, validate_agent_output)],
                    ),
                ],
                "SubagentStart": [
                    HookMatcher(
                        hooks=[cast(HookCallback, on_subagent_start)],
                    ),
                ],
                "SubagentStop": [
                    HookMatcher(
                        hooks=[cast(HookCallback, on_subagent_stop)],
                    ),
                ],
            },
            agents=AGENT_DEFINITIONS,
            max_turns=500,
            cwd=str(args.worktree_dir.resolve()),
            settings=str(settings_file.resolve()),
            extra_args={"replay-user-messages": None},
            stderr=lambda line: print(f"[Worker {args.issue_id}] {line}", flush=True),
        )
    )


def write_result(result_path: Path, result: dict) -> None:
    """Write worker result to JSON file."""
    result_path.parent.mkdir(parents=True, exist_ok=True)
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)


async def run_worker(args: argparse.Namespace) -> dict:
    """
    Execute the full pipeline for a single issue.

    Returns:
        Result dict with issue_id, status, branch, files_changed, duration_seconds, error.
    """
    start_time = time.monotonic()
    issue_id = args.issue_id

    print(f"\n[Worker {issue_id}] Starting: {args.issue_title}")
    print(f"[Worker {issue_id}] Worktree: {args.worktree_dir}")
    print(f"[Worker {issue_id}] Branch: {args.branch}")

    # Import SDK types here (inside async context)
    from claude_agent_sdk import (
        AssistantMessage,
        TextBlock,
        ToolResultBlock,
        ToolUseBlock,
        UserMessage,
    )

    try:
        prompt = build_worker_prompt(args)
        client = create_worker_client(args)

        response_text = ""
        async with client:
            await client.query(prompt)

            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            response_text += block.text
                            print(block.text, end="", flush=True)
                        elif isinstance(block, ToolUseBlock):
                            print(f"\n[Worker {issue_id}][Tool: {block.name}]", flush=True)
                elif isinstance(msg, UserMessage):
                    for block in msg.content:
                        if isinstance(block, ToolResultBlock):
                            is_error = bool(block.is_error) if block.is_error else False
                            if is_error:
                                print(f"[Worker {issue_id}]   [Error] {str(block.content)[:200]}", flush=True)
                            elif "blocked" in str(block.content).lower():
                                print(f"[Worker {issue_id}]   [BLOCKED] {block.content}", flush=True)
                            else:
                                print(f"[Worker {issue_id}]   [Done]", flush=True)

        duration = time.monotonic() - start_time

        # Try to extract structured result from response
        # The worker prompt asks the agent to output JSON
        files_changed: list[str] = []
        status = "success"

        # Look for JSON block in response
        if '```json' in response_text:
            try:
                json_start = response_text.index('```json') + 7
                json_end = response_text.index('```', json_start)
                result_json = json.loads(response_text[json_start:json_end].strip())
                if result_json.get("status") == "error":
                    status = "error"
                files_changed = result_json.get("files_changed", [])
            except (ValueError, json.JSONDecodeError):
                pass  # Best-effort parsing

        result = {
            "issue_id": issue_id,
            "status": status,
            "branch": args.branch,
            "files_changed": files_changed,
            "duration_seconds": round(duration, 1),
            "error": "" if status == "success" else "Worker reported error in response",
        }

        print(f"\n[Worker {issue_id}] Completed in {duration:.0f}s — status: {status}")
        return result

    except Exception as e:
        duration = time.monotonic() - start_time
        error_msg = f"{type(e).__name__}: {e}"
        print(f"\n[Worker {issue_id}] FAILED after {duration:.0f}s: {error_msg}")
        traceback.print_exc()

        return {
            "issue_id": issue_id,
            "status": "error",
            "branch": args.branch,
            "files_changed": [],
            "duration_seconds": round(duration, 1),
            "error": error_msg,
        }


def main() -> int:
    """Worker process entry point."""
    args = parse_args()

    try:
        result = asyncio.run(run_worker(args))
        write_result(args.result_path, result)
        return 0 if result["status"] == "success" else 1
    except KeyboardInterrupt:
        print(f"\n[Worker {args.issue_id}] Interrupted")
        write_result(args.result_path, {
            "issue_id": args.issue_id,
            "status": "error",
            "branch": args.branch,
            "files_changed": [],
            "duration_seconds": 0,
            "error": "Interrupted by user",
        })
        return 130
    except Exception as e:
        print(f"\n[Worker {args.issue_id}] Fatal error: {e}")
        traceback.print_exc()
        write_result(args.result_path, {
            "issue_id": args.issue_id,
            "status": "error",
            "branch": args.branch,
            "files_changed": [],
            "duration_seconds": 0,
            "error": str(e),
        })
        return 1


if __name__ == "__main__":
    sys.exit(main())
