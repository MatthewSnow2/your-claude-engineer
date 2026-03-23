"""Skill packaging functionality."""

import hashlib
import json
import sys
import tarfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Dict, List

from .models import SkillManifest, SkillPackage

# Security constants
MAX_PACKAGE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB per file


class SkillPackager:
    """Handles creating and extracting .skillpkg files."""

    def __init__(self):
        """Initialize packager."""
        pass

    def package_skill(
        self, skill_dir: Path, manifest: SkillManifest, output_path: Path = None
    ) -> SkillPackage:
        """
        Package a skill directory into a .skillpkg file.

        Args:
            skill_dir: Path to skill directory
            manifest: Validated skill manifest
            output_path: Optional output path for .skillpkg file

        Returns:
            SkillPackage object
        """
        # Collect source files
        source_files = self._collect_source_files(skill_dir, manifest)

        # Calculate checksum
        checksum = self._calculate_checksum(source_files, manifest)

        # Calculate package size
        package_size = sum(len(content) for content in source_files.values())

        # Create package object
        package = SkillPackage(
            manifest=manifest,
            source_files=source_files,
            package_size=package_size,
            checksum=checksum,
            created_at=datetime.now(timezone.utc),
        )

        # Write to file if output_path provided
        if output_path:
            self._write_package_file(package, output_path)

        return package

    def _collect_source_files(
        self, skill_dir: Path, manifest: SkillManifest
    ) -> Dict[str, bytes]:
        """
        Collect all source files that should be included in package.

        Args:
            skill_dir: Skill directory path
            manifest: Skill manifest

        Returns:
            Dictionary mapping relative paths to file contents
        """
        source_files = {}

        # Always include skill.json
        manifest_path = skill_dir / "skill.json"
        if manifest_path.exists():
            source_files["skill.json"] = manifest_path.read_bytes()

        # Include main module
        main_module_path = skill_dir / manifest.main_module
        if main_module_path.exists():
            source_files[manifest.main_module] = main_module_path.read_bytes()

        # Include all Python files in skill directory
        for py_file in skill_dir.rglob("*.py"):
            if py_file.is_file():
                rel_path = py_file.relative_to(skill_dir)
                # Skip __pycache__ and other unwanted files
                if "__pycache__" not in str(rel_path) and ".venv" not in str(rel_path):
                    source_files[str(rel_path)] = py_file.read_bytes()

        # Include requirements.txt if exists
        req_file = skill_dir / "requirements.txt"
        if req_file.exists():
            source_files["requirements.txt"] = req_file.read_bytes()

        # Include README if exists
        for readme_name in ["README.md", "README.txt", "README"]:
            readme_path = skill_dir / readme_name
            if readme_path.exists():
                source_files[readme_name] = readme_path.read_bytes()
                break

        return source_files

    def _calculate_checksum(
        self, source_files: Dict[str, bytes], manifest: SkillManifest
    ) -> str:
        """
        Calculate SHA256 checksum for package contents.

        Args:
            source_files: Source files dictionary
            manifest: Skill manifest

        Returns:
            Hex-encoded SHA256 hash
        """
        hasher = hashlib.sha256()

        # Hash manifest
        manifest_json = manifest.model_dump_json(indent=2)
        hasher.update(manifest_json.encode())

        # Hash source files in sorted order for consistency
        for filename in sorted(source_files.keys()):
            hasher.update(filename.encode())
            hasher.update(source_files[filename])

        return hasher.hexdigest()

    def _write_package_file(self, package: SkillPackage, output_path: Path):
        """
        Write package to .skillpkg tarball file.

        Args:
            package: SkillPackage to write
            output_path: Output file path
        """
        with tarfile.open(output_path, "w:gz") as tar:
            # Add manifest
            manifest_json = package.manifest.model_dump_json(indent=2)
            manifest_bytes = manifest_json.encode()
            manifest_info = tarfile.TarInfo(name="skill.json")
            manifest_info.size = len(manifest_bytes)
            manifest_info.mtime = int(package.created_at.timestamp())
            manifest_info.mode = 0o644  # Safe file permissions
            tar.addfile(manifest_info, BytesIO(manifest_bytes))

            # Add source files
            for filename, content in package.source_files.items():
                if filename == "skill.json":
                    continue  # Already added
                file_info = tarfile.TarInfo(name=filename)
                file_info.size = len(content)
                file_info.mtime = int(package.created_at.timestamp())
                # Set safe permissions: 0o755 for .py files (executable), 0o644 for others
                if filename.endswith('.py'):
                    file_info.mode = 0o755
                else:
                    file_info.mode = 0o644
                tar.addfile(file_info, BytesIO(content))

            # Add metadata file
            metadata = {
                "package_size": package.package_size,
                "checksum": package.checksum,
                "created_at": package.created_at.isoformat(),
                "skill_name": package.manifest.name,
                "skill_version": package.manifest.version,
            }
            metadata_json = json.dumps(metadata, indent=2).encode()
            metadata_info = tarfile.TarInfo(name=".skillpkg-metadata")
            metadata_info.size = len(metadata_json)
            metadata_info.mtime = int(package.created_at.timestamp())
            metadata_info.mode = 0o644  # Safe file permissions
            tar.addfile(metadata_info, BytesIO(metadata_json))

    def extract_package(self, package_path: Path, output_dir: Path) -> SkillManifest:
        """
        Extract a .skillpkg file to a directory with security validation.

        Args:
            package_path: Path to .skillpkg file
            output_dir: Output directory

        Returns:
            Extracted SkillManifest

        Raises:
            ValueError: If package fails security validation
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        output_dir = output_dir.resolve()  # Get absolute path

        with tarfile.open(package_path, "r:gz") as tar:
            # Security validation: check total size
            total_size = sum(member.size for member in tar.getmembers() if member.isfile())
            if total_size > MAX_PACKAGE_SIZE:
                raise ValueError(f"Package too large: {total_size} bytes (max {MAX_PACKAGE_SIZE})")

            # Security validation: check each member before extraction
            for member in tar.getmembers():
                # Check for path traversal
                member_path = (output_dir / member.name).resolve()
                if not member_path.is_relative_to(output_dir):
                    raise ValueError(f"Attempted path traversal: {member.name}")

                # Check for symlinks
                if member.issym() or member.islnk():
                    raise ValueError(f"Symlinks not allowed in packages: {member.name}")

                # Check individual file size
                if member.isfile() and member.size > MAX_FILE_SIZE:
                    raise ValueError(f"File too large: {member.name} ({member.size} bytes)")

            # Extract with filter parameter for Python 3.12+ if available
            if sys.version_info >= (3, 12):
                try:
                    tar.extractall(output_dir, filter='data')
                except TypeError:
                    # Fallback for Python versions that don't support filter
                    tar.extractall(output_dir)
            else:
                tar.extractall(output_dir)

        # Load and return manifest
        manifest_path = output_dir / "skill.json"
        with open(manifest_path) as f:
            manifest_data = json.load(f)

        return SkillManifest(**manifest_data)


def create_package(skill_dir: Path, output_path: Path = None) -> SkillPackage:
    """
    Convenience function to package a skill.

    Args:
        skill_dir: Skill directory
        output_path: Optional output file path

    Returns:
        SkillPackage object
    """
    from .validation import SkillValidator

    # Validate first
    validator = SkillValidator()
    result, manifest = validator.validate_skill_directory(skill_dir)

    if not result.is_valid:
        raise ValueError(f"Skill validation failed:\n{result}")

    # Package
    packager = SkillPackager()
    return packager.package_skill(skill_dir, manifest, output_path)
