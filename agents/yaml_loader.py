"""
YAML Agent Loader
=================

Loads agent definitions from Agent Persona Academy YAML files.
Produces AgentDefinition objects compatible with the Claude Agent SDK.

This is an optional parallel path to the hardcoded definitions in definitions.py.
Use LOAD_AGENTS_FROM_YAML=true to activate.
"""

import os
from pathlib import Path
from typing import Any

import yaml

from claude_agent_sdk.types import AgentDefinition

from arcade_config import (
    get_linear_tools,
    get_github_tools,
    get_slack_tools,
    get_coding_tools,
    get_qa_tools,
    get_code_review_tools,
)

# Default Academy personas directory
ACADEMY_DIR = Path(os.environ.get(
    "ACADEMY_PERSONAS_DIR",
    str(Path.home() / "projects" / "agent-persona-academy" / "personas"),
))

# Prompts directory for prompt_file resolution
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# Map tool group names to resolver functions
TOOL_GROUPS: dict[str, list[str]] = {}


def _resolve_tool_groups() -> dict[str, list[str]]:
    """Lazily resolve tool groups from arcade_config."""
    if not TOOL_GROUPS:
        TOOL_GROUPS["linear"] = get_linear_tools() + ["Read", "Write", "Edit", "Glob"]
        TOOL_GROUPS["github"] = get_github_tools() + ["Read", "Write", "Edit", "Glob", "Bash"]
        TOOL_GROUPS["slack"] = get_slack_tools() + ["Read", "Write", "Edit", "Glob"]
        TOOL_GROUPS["coding"] = get_coding_tools()
        TOOL_GROUPS["qa"] = get_qa_tools()
        TOOL_GROUPS["code_review"] = get_code_review_tools()
        TOOL_GROUPS["file"] = ["Read", "Write", "Edit", "Glob", "Grep"]
        TOOL_GROUPS["file_readonly"] = ["Read", "Glob", "Grep"]
    return TOOL_GROUPS


def _resolve_tools(tools_config: dict[str, Any]) -> list[str]:
    """Resolve a tools configuration into a flat list of tool names."""
    groups = _resolve_tool_groups()
    result: list[str] = []

    for group_name in tools_config.get("groups", []):
        if group_name in groups:
            result.extend(groups[group_name])

    for tool in tools_config.get("additional", []):
        if tool not in result:
            result.append(tool)

    exclude = set(tools_config.get("exclude", []))
    if exclude:
        result = [t for t in result if t not in exclude]

    return result


def _load_prompt(prompt_file: str) -> str:
    """Load a prompt file from the prompts directory."""
    path = PROMPTS_DIR / prompt_file
    if not path.exists():
        # Try without extension
        path = PROMPTS_DIR / f"{prompt_file}.md"
    return path.read_text()


def _get_model_with_env(
    agent_name: str,
    yaml_model: str | None,
) -> str:
    """Get model from env var, falling back to YAML default, then to 'haiku'."""
    env_var = f"{agent_name.upper()}_AGENT_MODEL"
    env_value = os.environ.get(env_var, "").lower().strip()
    valid = ("haiku", "sonnet", "opus", "inherit")

    if env_value in valid:
        return env_value
    if yaml_model and yaml_model in valid:
        return yaml_model
    return "haiku"


def load_agent_from_yaml(persona_path: Path) -> AgentDefinition | None:
    """
    Load a single persona YAML and produce an AgentDefinition.

    Returns None if the persona has no agent_config section
    (identity-only personas used for prompt shaping, not agent instantiation).
    """
    yaml_file = persona_path / "persona.yaml" if persona_path.is_dir() else persona_path
    if not yaml_file.exists():
        return None

    with open(yaml_file) as f:
        data = yaml.safe_load(f)

    agent_config = data.get("agent_config")
    if not agent_config:
        return None

    # Derive agent name from directory
    agent_name = yaml_file.parent.name

    # Resolve prompt
    prompt_file = agent_config.get("prompt_file")
    if prompt_file:
        prompt = _load_prompt(prompt_file)
    else:
        prompt = f"You are {data['identity']['name']}, {data['identity']['role']}."

    # Resolve tools
    tools_config = agent_config.get("tools", {})
    tools = _resolve_tools(tools_config) if tools_config else None

    # Resolve model (env var > YAML > default)
    model = _get_model_with_env(agent_name, agent_config.get("model"))

    return AgentDefinition(
        description=agent_config.get("description", data["identity"]["role"]),
        prompt=prompt,
        tools=tools,
        model=model,
    )


def load_all_agents_from_yaml(
    personas_dir: Path | None = None,
) -> dict[str, AgentDefinition]:
    """
    Scan a personas directory and load all agent-capable personas.

    Only personas with an agent_config section are included.
    Identity-only personas are silently skipped.
    """
    base = personas_dir or ACADEMY_DIR
    agents: dict[str, AgentDefinition] = {}

    if not base.exists():
        return agents

    for persona_dir in sorted(base.iterdir()):
        if not persona_dir.is_dir():
            continue
        yaml_file = persona_dir / "persona.yaml"
        if not yaml_file.exists():
            continue

        agent = load_agent_from_yaml(persona_dir)
        if agent is not None:
            agents[persona_dir.name] = agent

    return agents
