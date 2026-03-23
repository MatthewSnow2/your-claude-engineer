"""Tests for skill packaging."""

import json
import tarfile

import pytest

from skillhub.core.models import SkillManifest
from skillhub.core.packaging import SkillPackager, create_package


def test_collect_source_files(sample_skill_dir, sample_manifest_data):
    """Test collecting source files from skill directory."""
    manifest = SkillManifest(**sample_manifest_data)
    packager = SkillPackager()

    source_files = packager._collect_source_files(sample_skill_dir, manifest)

    assert "skill.json" in source_files
    assert "main.py" in source_files
    assert len(source_files) >= 2


def test_calculate_checksum(sample_manifest_data):
    """Test checksum calculation."""
    manifest = SkillManifest(**sample_manifest_data)
    packager = SkillPackager()

    source_files = {"main.py": b"def test(): pass"}
    checksum = packager._calculate_checksum(source_files, manifest)

    assert isinstance(checksum, str)
    assert len(checksum) == 64  # SHA256 hex length


def test_package_skill(sample_skill_dir, sample_manifest_data):
    """Test packaging a skill."""
    manifest = SkillManifest(**sample_manifest_data)
    packager = SkillPackager()

    package = packager.package_skill(sample_skill_dir, manifest)

    assert package.manifest.name == "test-skill"
    assert package.manifest.version == "0.1.0"
    assert len(package.source_files) >= 2
    assert package.package_size > 0
    assert len(package.checksum) == 64


def test_write_package_file(sample_skill_dir, sample_manifest_data, tmp_path):
    """Test writing package to .skillpkg file."""
    manifest = SkillManifest(**sample_manifest_data)
    packager = SkillPackager()

    output_path = tmp_path / "test-skill.skillpkg"
    package = packager.package_skill(sample_skill_dir, manifest, output_path)

    assert output_path.exists()
    assert output_path.stat().st_size > 0

    # Verify tarball contents
    with tarfile.open(output_path, "r:gz") as tar:
        names = tar.getnames()
        assert "skill.json" in names
        assert "main.py" in names
        assert ".skillpkg-metadata" in names


def test_extract_package(sample_skill_dir, sample_manifest_data, tmp_path):
    """Test extracting a .skillpkg file."""
    manifest = SkillManifest(**sample_manifest_data)
    packager = SkillPackager()

    # Create package
    package_path = tmp_path / "test-skill.skillpkg"
    packager.package_skill(sample_skill_dir, manifest, package_path)

    # Extract to new directory
    extract_dir = tmp_path / "extracted"
    extracted_manifest = packager.extract_package(package_path, extract_dir)

    assert extracted_manifest.name == "test-skill"
    assert (extract_dir / "skill.json").exists()
    assert (extract_dir / "main.py").exists()


def test_create_package_convenience_function(sample_skill_dir, tmp_path):
    """Test create_package convenience function."""
    output_path = tmp_path / "test.skillpkg"
    package = create_package(sample_skill_dir, output_path)

    assert package.manifest.name == "test-skill"
    assert output_path.exists()


def test_create_package_validation_failure(temp_skill_dir):
    """Test create_package fails with invalid skill."""
    # Create invalid manifest
    manifest_file = temp_skill_dir / "skill.json"
    manifest_file.write_text(json.dumps({"name": "test"}))

    with pytest.raises(ValueError, match="validation failed"):
        create_package(temp_skill_dir)


def test_package_includes_readme(sample_skill_dir, sample_manifest_data, tmp_path):
    """Test package includes README if present."""
    # Add README
    readme_file = sample_skill_dir / "README.md"
    readme_file.write_text("# Test Skill\n\nThis is a test.")

    manifest = SkillManifest(**sample_manifest_data)
    packager = SkillPackager()
    package = packager.package_skill(sample_skill_dir, manifest)

    assert "README.md" in package.source_files


def test_package_excludes_pycache(sample_skill_dir, sample_manifest_data):
    """Test package excludes __pycache__ directories."""
    # Create __pycache__ directory
    pycache_dir = sample_skill_dir / "__pycache__"
    pycache_dir.mkdir()
    (pycache_dir / "test.pyc").write_bytes(b"compiled")

    manifest = SkillManifest(**sample_manifest_data)
    packager = SkillPackager()
    package = packager.package_skill(sample_skill_dir, manifest)

    # Should not include __pycache__ files
    assert not any("__pycache__" in filename for filename in package.source_files.keys())


def test_extract_package_rejects_path_traversal(tmp_path):
    """Test that extraction rejects malicious path traversal attempts."""
    import tarfile
    from io import BytesIO

    # Create a malicious tarball with path traversal
    malicious_package = tmp_path / "malicious.skillpkg"
    with tarfile.open(malicious_package, "w:gz") as tar:
        # Try to write outside extraction directory
        malicious_content = b"malicious payload"
        info = tarfile.TarInfo(name="../../../etc/passwd")
        info.size = len(malicious_content)
        tar.addfile(info, BytesIO(malicious_content))

        # Add a valid manifest to make it look legitimate
        manifest_content = json.dumps({
            "name": "test-skill",
            "version": "0.1.0",
            "description": "Test",
            "author": "Test",
            "main_module": "main.py",
            "capabilities": [],
            "license": "MIT"
        }).encode()
        manifest_info = tarfile.TarInfo(name="skill.json")
        manifest_info.size = len(manifest_content)
        tar.addfile(manifest_info, BytesIO(manifest_content))

    # Attempt to extract should raise ValueError
    packager = SkillPackager()
    extract_dir = tmp_path / "extracted"

    with pytest.raises(ValueError, match="path traversal"):
        packager.extract_package(malicious_package, extract_dir)


def test_extract_package_rejects_symlinks(tmp_path):
    """Test that extraction rejects packages with symlinks."""
    import tarfile
    from io import BytesIO

    # Create a package with a symlink
    symlink_package = tmp_path / "symlink.skillpkg"
    with tarfile.open(symlink_package, "w:gz") as tar:
        # Add a symlink
        symlink_info = tarfile.TarInfo(name="malicious_link")
        symlink_info.type = tarfile.SYMTYPE
        symlink_info.linkname = "/etc/passwd"
        tar.addfile(symlink_info)

        # Add a valid manifest
        manifest_content = json.dumps({
            "name": "test-skill",
            "version": "0.1.0",
            "description": "Test",
            "author": "Test",
            "main_module": "main.py",
            "capabilities": [],
            "license": "MIT"
        }).encode()
        manifest_info = tarfile.TarInfo(name="skill.json")
        manifest_info.size = len(manifest_content)
        tar.addfile(manifest_info, BytesIO(manifest_content))

    # Attempt to extract should raise ValueError
    packager = SkillPackager()
    extract_dir = tmp_path / "extracted"

    with pytest.raises(ValueError, match="Symlinks not allowed"):
        packager.extract_package(symlink_package, extract_dir)


def test_extract_package_rejects_oversized_package(tmp_path):
    """Test that extraction rejects packages exceeding size limit."""
    import tarfile
    from io import BytesIO

    # Create a package that exceeds MAX_PACKAGE_SIZE
    oversized_package = tmp_path / "oversized.skillpkg"
    with tarfile.open(oversized_package, "w:gz") as tar:
        # Create a file larger than MAX_PACKAGE_SIZE (100MB)
        huge_content = b"x" * (101 * 1024 * 1024)  # 101 MB
        info = tarfile.TarInfo(name="huge_file.bin")
        info.size = len(huge_content)
        tar.addfile(info, BytesIO(huge_content))

        # Add a valid manifest
        manifest_content = json.dumps({
            "name": "test-skill",
            "version": "0.1.0",
            "description": "Test",
            "author": "Test",
            "main_module": "main.py",
            "capabilities": [],
            "license": "MIT"
        }).encode()
        manifest_info = tarfile.TarInfo(name="skill.json")
        manifest_info.size = len(manifest_content)
        tar.addfile(manifest_info, BytesIO(manifest_content))

    # Attempt to extract should raise ValueError
    packager = SkillPackager()
    extract_dir = tmp_path / "extracted"

    with pytest.raises(ValueError, match="Package too large"):
        packager.extract_package(oversized_package, extract_dir)
