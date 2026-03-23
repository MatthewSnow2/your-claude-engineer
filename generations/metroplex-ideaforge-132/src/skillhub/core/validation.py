"""Skill manifest validation logic."""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import ValidationError

from .models import SkillManifest


class ValidationResult:
    """Result of skill validation."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.is_valid: bool = True

    def add_error(self, message: str):
        """Add validation error."""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str):
        """Add validation warning."""
        self.warnings.append(message)

    def __str__(self) -> str:
        """Format validation result."""
        lines = []
        if self.errors:
            lines.append("ERRORS:")
            for error in self.errors:
                lines.append(f"  - {error}")
        if self.warnings:
            lines.append("WARNINGS:")
            for warning in self.warnings:
                lines.append(f"  - {warning}")
        if self.is_valid and not self.warnings:
            lines.append("Validation passed successfully.")
        return "\n".join(lines)


class SkillValidator:
    """Validates skill manifests against Agent Skills standard."""

    def __init__(self):
        """Initialize validator."""
        pass

    def validate_manifest_file(self, manifest_path: Path) -> Tuple[ValidationResult, Optional[SkillManifest]]:
        """
        Validate a skill.json manifest file.

        Args:
            manifest_path: Path to skill.json file

        Returns:
            Tuple of (ValidationResult, SkillManifest or None)
        """
        result = ValidationResult()

        # Check file exists
        if not manifest_path.exists():
            result.add_error(f"Manifest file not found: {manifest_path}")
            return result, None

        # Load and parse JSON
        try:
            with open(manifest_path, "r") as f:
                manifest_data = json.load(f)
        except json.JSONDecodeError as e:
            result.add_error(f"Invalid JSON: {e}")
            return result, None
        except Exception as e:
            result.add_error(f"Failed to read manifest: {e}")
            return result, None

        # Validate against Pydantic model
        try:
            manifest = SkillManifest(**manifest_data)
        except ValidationError as e:
            for error in e.errors():
                field = ".".join(str(loc) for loc in error["loc"])
                result.add_error(f"{field}: {error['msg']}")
            return result, None

        # Additional validation checks
        self._validate_capabilities(manifest, result)
        self._validate_mcp_tools(manifest, result)
        self._validate_dependencies(manifest, result)

        return result, manifest

    def _validate_capabilities(self, manifest: SkillManifest, result: ValidationResult):
        """Validate skill capabilities."""
        if not manifest.capabilities:
            result.add_warning("No capabilities defined")
            return

        for cap in manifest.capabilities:
            # Check input schema has 'type' field
            if "type" not in cap.input_schema:
                result.add_warning(
                    f"Capability '{cap.name}' input_schema missing 'type' field"
                )

            # Check output schema has 'type' field
            if "type" not in cap.output_schema:
                result.add_warning(
                    f"Capability '{cap.name}' output_schema missing 'type' field"
                )

    def _validate_mcp_tools(self, manifest: SkillManifest, result: ValidationResult):
        """Validate MCP tool definitions."""
        if not manifest.mcp_tools:
            result.add_warning("No MCP tools defined")
            return

        for tool in manifest.mcp_tools:
            # Check input schema structure
            if "type" not in tool.inputSchema:
                result.add_warning(f"MCP tool '{tool.name}' inputSchema missing 'type' field")

            # Validate function_path format
            if "." not in tool.function_path:
                result.add_warning(
                    f"MCP tool '{tool.name}' function_path should be module.function format"
                )

    def _validate_dependencies(self, manifest: SkillManifest, result: ValidationResult):
        """Validate dependency specifications."""
        all_deps = {**manifest.dependencies, **manifest.dev_dependencies}

        for dep_name, dep_version in all_deps.items():
            # Check version format (basic check)
            if not dep_version:
                result.add_warning(f"Dependency '{dep_name}' has empty version")

    def validate_skill_directory(self, skill_dir: Path) -> Tuple[ValidationResult, Optional[SkillManifest]]:
        """
        Validate a complete skill directory.

        Args:
            skill_dir: Path to skill directory

        Returns:
            Tuple of (ValidationResult, SkillManifest or None)
        """
        result = ValidationResult()

        # Check directory exists
        if not skill_dir.exists() or not skill_dir.is_dir():
            result.add_error(f"Skill directory not found: {skill_dir}")
            return result, None

        # Validate manifest
        manifest_path = skill_dir / "skill.json"
        manifest_result, manifest = self.validate_manifest_file(manifest_path)

        result.errors.extend(manifest_result.errors)
        result.warnings.extend(manifest_result.warnings)
        result.is_valid = manifest_result.is_valid

        if not manifest:
            return result, None

        # Check main module exists
        main_module_path = skill_dir / manifest.main_module
        if not main_module_path.exists():
            result.add_error(f"Main module not found: {manifest.main_module}")

        return result, manifest


def validate_skill(manifest_path: Path) -> Tuple[bool, str]:
    """
    Simple validation function for CLI use.

    Args:
        manifest_path: Path to skill.json

    Returns:
        Tuple of (is_valid, message)
    """
    validator = SkillValidator()
    result, manifest = validator.validate_manifest_file(manifest_path)

    return result.is_valid, str(result)
