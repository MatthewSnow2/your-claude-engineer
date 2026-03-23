"""Pytest configuration and fixtures."""

import json
import shutil
from pathlib import Path

import pytest


@pytest.fixture
def temp_skill_dir(tmp_path):
    """Create a temporary skill directory."""
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    return skill_dir


@pytest.fixture
def sample_manifest_data():
    """Return sample skill manifest data."""
    return {
        "name": "test-skill",
        "version": "0.1.0",
        "description": "A test skill",
        "author": "Test Author",
        "agent_skills_version": "1.0.0",
        "capabilities": [
            {
                "name": "test_capability",
                "description": "Test capability",
                "input_schema": {
                    "type": "object",
                    "properties": {"input": {"type": "string"}},
                },
                "output_schema": {"type": "object", "properties": {"result": {"type": "string"}}},
                "required_permissions": [],
            }
        ],
        "dependencies": {},
        "dev_dependencies": {},
        "main_module": "main.py",
        "mcp_tools": [
            {
                "name": "test_tool",
                "description": "Test tool",
                "inputSchema": {"type": "object", "properties": {"input": {"type": "string"}}},
                "function_path": "main.execute",
            }
        ],
        "compatibility": {
            "claude_code": True,
            "custom_agents": [],
            "runtime_requirements": [],
        },
        "license": "MIT",
        "keywords": ["test"],
        "repository": None,
    }


@pytest.fixture
def sample_skill_dir(temp_skill_dir, sample_manifest_data):
    """Create a complete sample skill directory."""
    # Create manifest
    manifest_file = temp_skill_dir / "skill.json"
    manifest_file.write_text(json.dumps(sample_manifest_data, indent=2))

    # Create main module
    main_file = temp_skill_dir / "main.py"
    main_file.write_text(
        '''def execute(input: str) -> dict:
    return {"result": f"Processed: {input}"}
'''
    )

    # Create test file
    test_file = temp_skill_dir / "test_skill.py"
    test_file.write_text(
        '''import pytest
from main import execute

def test_execute():
    result = execute("test")
    assert "result" in result
'''
    )

    return temp_skill_dir


@pytest.fixture
def local_registry(tmp_path):
    """Create a local registry directory for testing."""
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()

    # Create index
    index_file = registry_dir / "index.json"
    index_file.write_text(json.dumps({"skills": {}}, indent=2))

    return registry_dir


@pytest.fixture
def cleanup_test_skills():
    """Clean up test skill directories after tests."""
    yield
    # Cleanup logic if needed
    test_dirs = [Path.cwd() / name for name in ["test-skill", "webscraper-skill"]]
    for test_dir in test_dirs:
        if test_dir.exists() and test_dir.is_dir():
            shutil.rmtree(test_dir, ignore_errors=True)
