"""Skill initialization command."""

import json
from pathlib import Path

import click


@click.command()
@click.argument("skill_name")
@click.option("--author", default="", help="Author name")
@click.option("--description", default="", help="Skill description")
def init(skill_name: str, author: str, description: str):
    """Initialize a new skill directory with template files."""
    # Create skill directory
    skill_dir = Path.cwd() / skill_name
    if skill_dir.exists():
        click.echo(f"Error: Directory '{skill_name}' already exists")
        return

    skill_dir.mkdir(parents=True)

    # Create skill.json from template
    manifest = {
        "name": skill_name,
        "version": "0.1.0",
        "description": description or f"A {skill_name} agent skill",
        "author": author or "Your Name",
        "agent_skills_version": "1.0.0",
        "capabilities": [
            {
                "name": "main_capability",
                "description": "Main skill capability",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "input": {"type": "string", "description": "Input parameter"}
                    },
                    "required": ["input"],
                },
                "output_schema": {
                    "type": "object",
                    "properties": {"result": {"type": "string", "description": "Result"}},
                },
                "required_permissions": [],
            }
        ],
        "dependencies": {},
        "dev_dependencies": {},
        "main_module": "main.py",
        "mcp_tools": [
            {
                "name": f"{skill_name}_execute",
                "description": f"Execute {skill_name} skill",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "input": {"type": "string", "description": "Input parameter"}
                    },
                    "required": ["input"],
                },
                "function_path": "main.execute",
            }
        ],
        "compatibility": {
            "claude_code": True,
            "custom_agents": [],
            "runtime_requirements": ["python>=3.11"],
        },
        "license": "MIT",
        "keywords": [skill_name, "agent", "skill"],
        "repository": None,
    }

    manifest_file = skill_dir / "skill.json"
    manifest_file.write_text(json.dumps(manifest, indent=2))

    # Create main.py from template
    main_py_content = '''"""Main module for {skill_name} skill."""


def execute(input: str) -> dict:
    """
    Execute the main skill capability.

    Args:
        input: Input parameter

    Returns:
        Dictionary with result
    """
    # TODO: Implement skill logic here
    result = f"Processed: {{input}}"

    return {{"result": result}}


if __name__ == "__main__":
    # Test the skill
    test_input = "test input"
    result = execute(test_input)
    print(f"Result: {{result}}")
'''.format(
        skill_name=skill_name
    )

    main_file = skill_dir / "main.py"
    main_file.write_text(main_py_content)

    # Create test file
    test_content = '''"""Tests for {skill_name} skill."""

import pytest
from main import execute


def test_execute():
    """Test basic execution."""
    result = execute("test")
    assert "result" in result
    assert "test" in result["result"].lower()
'''.format(
        skill_name=skill_name
    )

    test_file = skill_dir / "test_skill.py"
    test_file.write_text(test_content)

    # Create README
    readme_content = f"""# {skill_name}

{description or f"A {skill_name} agent skill"}

## Installation

```bash
skillhub install {skill_name}
```

## Usage

This skill provides the following capabilities:
- main_capability: Main skill capability

## Development

To test this skill locally:

```bash
python main.py
```

To run tests:

```bash
pytest test_skill.py
```

## Publishing

To publish this skill:

```bash
skillhub publish
```
"""

    readme_file = skill_dir / "README.md"
    readme_file.write_text(readme_content)

    # Create requirements.txt
    requirements_file = skill_dir / "requirements.txt"
    requirements_file.write_text("# Add your skill dependencies here\n")

    click.echo(f"Initialized skill '{skill_name}' in {skill_dir}")
    click.echo(f"")
    click.echo(f"Next steps:")
    click.echo(f"  cd {skill_name}")
    click.echo(f"  # Edit skill.json and main.py to implement your skill")
    click.echo(f"  skillhub validate")
    click.echo(f"  skillhub publish")
