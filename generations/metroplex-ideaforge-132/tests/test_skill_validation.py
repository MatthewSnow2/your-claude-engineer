"""Tests for skill validation."""

import json

import pytest

from skillhub.core.models import SkillManifest
from skillhub.core.validation import SkillValidator, ValidationResult


def test_validation_result():
    """Test ValidationResult class."""
    result = ValidationResult()
    assert result.is_valid is True
    assert len(result.errors) == 0
    assert len(result.warnings) == 0

    result.add_error("Test error")
    assert result.is_valid is False
    assert len(result.errors) == 1

    result.add_warning("Test warning")
    assert len(result.warnings) == 1


def test_validate_valid_manifest(sample_skill_dir):
    """Test validation of valid manifest."""
    validator = SkillValidator()
    result, manifest = validator.validate_manifest_file(sample_skill_dir / "skill.json")

    assert result.is_valid is True
    assert manifest is not None
    assert manifest.name == "test-skill"
    assert manifest.version == "0.1.0"


def test_validate_missing_manifest(temp_skill_dir):
    """Test validation of missing manifest."""
    validator = SkillValidator()
    result, manifest = validator.validate_manifest_file(temp_skill_dir / "skill.json")

    assert result.is_valid is False
    assert manifest is None
    assert "not found" in result.errors[0]


def test_validate_invalid_json(temp_skill_dir):
    """Test validation of invalid JSON."""
    manifest_file = temp_skill_dir / "skill.json"
    manifest_file.write_text("{invalid json")

    validator = SkillValidator()
    result, manifest = validator.validate_manifest_file(manifest_file)

    assert result.is_valid is False
    assert manifest is None
    assert any("JSON" in error for error in result.errors)


def test_validate_missing_required_fields(temp_skill_dir):
    """Test validation with missing required fields."""
    manifest_file = temp_skill_dir / "skill.json"
    manifest_file.write_text(json.dumps({"name": "test"}))

    validator = SkillValidator()
    result, manifest = validator.validate_manifest_file(manifest_file)

    assert result.is_valid is False
    assert manifest is None
    assert len(result.errors) > 0


def test_validate_invalid_version_format(temp_skill_dir, sample_manifest_data):
    """Test validation with invalid version format."""
    sample_manifest_data["version"] = "1.0"  # Invalid - needs X.Y.Z

    manifest_file = temp_skill_dir / "skill.json"
    manifest_file.write_text(json.dumps(sample_manifest_data))

    validator = SkillValidator()
    result, manifest = validator.validate_manifest_file(manifest_file)

    assert result.is_valid is False
    assert manifest is None


def test_validate_invalid_skill_name(temp_skill_dir, sample_manifest_data):
    """Test validation with invalid skill name."""
    sample_manifest_data["name"] = "invalid name!"  # Contains invalid characters

    manifest_file = temp_skill_dir / "skill.json"
    manifest_file.write_text(json.dumps(sample_manifest_data))

    validator = SkillValidator()
    result, manifest = validator.validate_manifest_file(manifest_file)

    assert result.is_valid is False
    assert manifest is None


def test_validate_skill_directory(sample_skill_dir):
    """Test validation of complete skill directory."""
    validator = SkillValidator()
    result, manifest = validator.validate_skill_directory(sample_skill_dir)

    assert result.is_valid is True
    assert manifest is not None


def test_validate_skill_directory_missing_main_module(sample_skill_dir):
    """Test validation fails if main module missing."""
    # Remove main module
    (sample_skill_dir / "main.py").unlink()

    validator = SkillValidator()
    result, manifest = validator.validate_skill_directory(sample_skill_dir)

    assert result.is_valid is False
    assert any("Main module not found" in error for error in result.errors)


def test_pydantic_model_validation():
    """Test Pydantic model validation directly."""
    # Valid manifest
    valid_data = {
        "name": "test-skill",
        "version": "1.0.0",
        "description": "Test",
        "author": "Author",
        "capabilities": [],
        "main_module": "main.py",
        "license": "MIT",
    }
    manifest = SkillManifest(**valid_data)
    assert manifest.name == "test-skill"

    # Invalid version
    invalid_data = valid_data.copy()
    invalid_data["version"] = "invalid"
    with pytest.raises(Exception):
        SkillManifest(**invalid_data)

    # Invalid name
    invalid_data = valid_data.copy()
    invalid_data["name"] = "invalid name!"
    with pytest.raises(Exception):
        SkillManifest(**invalid_data)


def test_validation_warnings_no_capabilities(temp_skill_dir, sample_manifest_data):
    """Test validation generates warnings for missing capabilities."""
    sample_manifest_data["capabilities"] = []

    manifest_file = temp_skill_dir / "skill.json"
    manifest_file.write_text(json.dumps(sample_manifest_data))

    validator = SkillValidator()
    result, manifest = validator.validate_manifest_file(manifest_file)

    # Should have warnings but still be valid
    assert result.is_valid is True
    assert len(result.warnings) > 0
    assert any("capabilities" in warning.lower() for warning in result.warnings)
