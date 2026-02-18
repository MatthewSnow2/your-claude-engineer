"""
Agent Hooks: A2A Metrics & Persona Validation
==============================================

SDK hooks for tracking agent-to-agent metrics (SubagentStart/Stop)
and validating agent persona boundaries (PostToolUse on Task tool).
"""

import time

from claude_agent_sdk import PreToolUseHookInput
from claude_agent_sdk.types import HookContext, SyncHookJSONOutput

# Type aliases matching SDK hook signatures
SubagentStartHookInput = dict
SubagentStopHookInput = dict
PostToolUseHookInput = dict

# Track timing per agent invocation
_agent_timings: dict[str, float] = {}
_session_metrics: list[dict] = []


async def on_subagent_start(
    input_data: SubagentStartHookInput,
    tool_use_id: str | None = None,
    context: HookContext | None = None,
) -> SyncHookJSONOutput:
    """Track when a subagent starts for latency measurement."""
    agent_id = input_data.get("agent_id", "unknown")
    agent_type = input_data.get("agent_type", "unknown")
    _agent_timings[agent_id] = time.time()
    print(f"  [Metrics] Agent '{agent_type}' started (id: {agent_id})")
    return {}


async def on_subagent_stop(
    input_data: SubagentStopHookInput,
    tool_use_id: str | None = None,
    context: HookContext | None = None,
) -> SyncHookJSONOutput:
    """Track agent completion, calculate latency."""
    agent_id = input_data.get("agent_id", "unknown")
    agent_type = input_data.get("agent_type", "unknown")
    start_time = _agent_timings.pop(agent_id, None)
    duration_s = time.time() - start_time if start_time else 0

    metric = {
        "agent_id": agent_id,
        "agent_type": agent_type,
        "duration_seconds": round(duration_s, 2),
        "transcript_path": input_data.get("agent_transcript_path", ""),
    }
    _session_metrics.append(metric)
    print(f"  [Metrics] Agent '{agent_type}' completed in {duration_s:.1f}s (id: {agent_id})")
    return {}


async def validate_agent_output(
    input_data: PostToolUseHookInput,
    tool_use_id: str | None = None,
    context: HookContext | None = None,
) -> SyncHookJSONOutput:
    """Validate subagent output matches expected persona boundaries.

    Checks that read-only agents (qa, code_review) haven't modified files.
    Runs as a PostToolUse hook on the Task tool.
    """
    if input_data.get("tool_name") != "Task":
        return {}

    response = input_data.get("tool_response", "")
    tool_input = input_data.get("tool_input", {})
    agent_type = tool_input.get("subagent_type", "")

    # Persona validation: check agent stayed in its lane
    violations: list[str] = []
    response_lower = str(response).lower()

    if agent_type == "qa" and any(
        kw in response_lower
        for kw in ["wrote file", "created file", "edited file"]
    ):
        violations.append(
            "QA agent appears to have modified files (should be read-only)"
        )

    if agent_type == "code_review" and any(
        kw in response_lower
        for kw in ["wrote file", "created file", "edited file"]
    ):
        violations.append(
            "Code review agent appears to have modified files (should be read-only)"
        )

    if violations:
        context_msg = f"PERSONA VIOLATION: {'; '.join(violations)}"
        print(f"  [Validation] {context_msg}")
        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": context_msg,
            }
        }

    return {}


def get_session_metrics() -> list[dict]:
    """Return collected metrics for this session."""
    return _session_metrics.copy()


def reset_metrics() -> None:
    """Reset metrics for a new session."""
    _agent_timings.clear()
    _session_metrics.clear()
