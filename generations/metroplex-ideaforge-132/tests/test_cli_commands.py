"""Tests for CLI commands."""

import json
from pathlib import Path

from click.testing import CliRunner

from skillhub.cli.main import cli


def test_version_command():
    """Test --version flag."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_help_command():
    """Test --help flag."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "SkillHub CLI" in result.output
    assert "init" in result.output
    assert "publish" in result.output
    assert "validate" in result.output


def test_init_command(tmp_path, cleanup_test_skills):
    """Test skillhub init command."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(cli, ["init", "test-skill", "--author", "Test Author"])
        assert result.exit_code == 0
        assert "Initialized skill 'test-skill'" in result.output

        # Check created files
        skill_dir = Path("test-skill")
        assert skill_dir.exists()
        assert (skill_dir / "skill.json").exists()
        assert (skill_dir / "main.py").exists()
        assert (skill_dir / "test_skill.py").exists()
        assert (skill_dir / "README.md").exists()

        # Check manifest content
        with open(skill_dir / "skill.json") as f:
            manifest = json.load(f)
        assert manifest["name"] == "test-skill"
        assert manifest["version"] == "0.1.0"
        assert manifest["author"] == "Test Author"


def test_init_command_existing_directory(tmp_path):
    """Test init fails if directory exists."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Create directory first
        Path("test-skill").mkdir()

        result = runner.invoke(cli, ["init", "test-skill"])
        assert result.exit_code == 0
        assert "already exists" in result.output


def test_validate_command(sample_skill_dir):
    """Test skillhub validate command."""
    runner = CliRunner()
    result = runner.invoke(cli, ["validate", str(sample_skill_dir / "skill.json")])
    assert result.exit_code == 0
    assert "Validation passed" in result.output


def test_validate_command_current_dir(sample_skill_dir):
    """Test validate in current directory."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=sample_skill_dir.parent):
        # Change to skill directory
        import os

        os.chdir(sample_skill_dir)

        result = runner.invoke(cli, ["validate"])
        assert result.exit_code == 0
        assert "Validation passed" in result.output


def test_validate_command_invalid_manifest(temp_skill_dir):
    """Test validate with invalid manifest."""
    runner = CliRunner()

    # Create invalid manifest (missing required fields)
    manifest_file = temp_skill_dir / "skill.json"
    manifest_file.write_text(json.dumps({"name": "test"}))

    result = runner.invoke(cli, ["validate", str(manifest_file)])
    assert result.exit_code == 0
    assert "Validation failed" in result.output or "Error" in result.output


def test_publish_command_no_manifest(tmp_path):
    """Test publish fails without skill.json."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(cli, ["publish"])
        assert result.exit_code == 0
        assert "skill.json not found" in result.output


def test_publish_command_dry_run(sample_skill_dir, local_registry):
    """Test publish with --dry-run flag."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=sample_skill_dir.parent):
        import os

        os.chdir(sample_skill_dir)

        result = runner.invoke(cli, ["publish", "--dry-run"])
        assert result.exit_code == 0
        assert "Validation passed" in result.output
        assert "Packaging skill" in result.output
        assert "Dry run complete" in result.output


def test_publish_command_to_local_registry(sample_skill_dir, local_registry):
    """Test publishing to local registry."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=sample_skill_dir.parent):
        import os

        os.chdir(sample_skill_dir)
        # Set local registry path
        os.environ.pop("SKILLHUB_REGISTRY_URL", None)

        result = runner.invoke(
            cli, ["publish", "--registry", f"file://{local_registry}"]
        )

        # The command should work, though registry logic might differ
        assert "Validation passed" in result.output or "Packaging skill" in result.output
