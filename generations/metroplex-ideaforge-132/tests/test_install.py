"""Tests for skill discovery and installation features."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from skillhub.cli.main import cli
from skillhub.core.cache import SkillCacheManager
from skillhub.core.packaging import SkillPackager
from skillhub.core.registry import RegistryClient


def test_search_skills_empty_registry(local_registry):
    """Test searching in empty registry."""
    runner = CliRunner()
    result = runner.invoke(cli, ["search", "test", "--registry", str(local_registry)])

    assert result.exit_code == 0
    assert "No skills found" in result.output


def test_search_skills_with_results(local_registry, sample_skill_dir, sample_manifest_data):
    """Test searching with results."""
    # Publish a skill first
    packager = SkillPackager()
    manifest_path = sample_skill_dir / "skill.json"
    with open(manifest_path) as f:
        manifest_data = json.load(f)

    from skillhub.core.models import SkillManifest

    manifest = SkillManifest(**manifest_data)
    package = packager.package_skill(sample_skill_dir, manifest)

    client = RegistryClient(local_registry_path=local_registry)
    client.publish_skill(package)

    # Now search
    runner = CliRunner()
    result = runner.invoke(cli, ["search", "test", "--registry", str(local_registry)])

    assert result.exit_code == 0
    assert "test-skill" in result.output
    assert "v0.1.0" in result.output


def test_install_from_registry(local_registry, sample_skill_dir, tmp_path):
    """Test installing skill from registry."""
    # Publish a skill first
    packager = SkillPackager()
    manifest_path = sample_skill_dir / "skill.json"
    with open(manifest_path) as f:
        manifest_data = json.load(f)

    from skillhub.core.models import SkillManifest

    manifest = SkillManifest(**manifest_data)
    package = packager.package_skill(sample_skill_dir, manifest)

    client = RegistryClient(local_registry_path=local_registry)
    client.publish_skill(package)

    # Install the skill
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Set cache dir to isolated location
        import os

        cache_dir = Path.cwd() / ".skillhub-cache"
        os.environ["SKILLHUB_CACHE_DIR"] = str(cache_dir)

        result = runner.invoke(
            cli, ["install", "test-skill", "--registry", str(local_registry)]
        )

        assert result.exit_code == 0
        assert "Successfully installed" in result.output
        assert "test-skill" in result.output

        # Verify skill is cached
        cache_manager = SkillCacheManager(cache_dir)
        cached = cache_manager.get_cached_skill("test-skill")
        assert cached is not None
        assert cached.version == "0.1.0"

        # Clean up env
        del os.environ["SKILLHUB_CACHE_DIR"]


def test_install_specific_version(local_registry, sample_skill_dir, tmp_path):
    """Test installing specific version."""
    # Publish a skill
    packager = SkillPackager()
    manifest_path = sample_skill_dir / "skill.json"
    with open(manifest_path) as f:
        manifest_data = json.load(f)

    from skillhub.core.models import SkillManifest

    manifest = SkillManifest(**manifest_data)
    package = packager.package_skill(sample_skill_dir, manifest)

    client = RegistryClient(local_registry_path=local_registry)
    client.publish_skill(package)

    # Install with version spec
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        import os

        cache_dir = Path.cwd() / ".skillhub-cache"
        os.environ["SKILLHUB_CACHE_DIR"] = str(cache_dir)

        result = runner.invoke(
            cli, ["install", "test-skill@0.1.0", "--registry", str(local_registry)]
        )

        assert result.exit_code == 0
        assert "Successfully installed" in result.output

        # Verify version
        cache_manager = SkillCacheManager(cache_dir)
        cached = cache_manager.get_cached_skill("test-skill", "0.1.0")
        assert cached is not None
        assert cached.version == "0.1.0"

        del os.environ["SKILLHUB_CACHE_DIR"]


def test_install_from_skillpkg_file(sample_skill_dir, tmp_path):
    """Test installing from local .skillpkg file."""
    # Create a .skillpkg file
    packager = SkillPackager()
    manifest_path = sample_skill_dir / "skill.json"
    with open(manifest_path) as f:
        manifest_data = json.load(f)

    from skillhub.core.models import SkillManifest

    manifest = SkillManifest(**manifest_data)
    pkg_path = tmp_path / "test-skill.skillpkg"
    package = packager.package_skill(sample_skill_dir, manifest, pkg_path)

    # Install from file
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        import os

        cache_dir = Path.cwd() / ".skillhub-cache"
        os.environ["SKILLHUB_CACHE_DIR"] = str(cache_dir)

        result = runner.invoke(cli, ["install", str(pkg_path)])

        assert result.exit_code == 0
        assert "Successfully installed" in result.output

        # Verify installation
        cache_manager = SkillCacheManager(cache_dir)
        cached = cache_manager.get_cached_skill("test-skill")
        assert cached is not None

        del os.environ["SKILLHUB_CACHE_DIR"]


def test_install_with_save_dev(local_registry, sample_skill_dir, tmp_path):
    """Test installing with --save-dev flag."""
    # Publish a skill
    packager = SkillPackager()
    manifest_path = sample_skill_dir / "skill.json"
    with open(manifest_path) as f:
        manifest_data = json.load(f)

    from skillhub.core.models import SkillManifest

    manifest = SkillManifest(**manifest_data)
    package = packager.package_skill(sample_skill_dir, manifest)

    client = RegistryClient(local_registry_path=local_registry)
    client.publish_skill(package)

    # Create a skill.json in working directory
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        import os

        cache_dir = Path.cwd() / ".skillhub-cache"
        os.environ["SKILLHUB_CACHE_DIR"] = str(cache_dir)

        # Create skill.json
        skill_json = Path.cwd() / "skill.json"
        skill_json.write_text(json.dumps(manifest_data, indent=2))

        # Install with --save-dev
        result = runner.invoke(
            cli,
            ["install", "test-skill", "--save-dev", "--registry", str(local_registry)],
        )

        assert result.exit_code == 0
        assert "dev_dependencies" in result.output

        # Verify skill.json was updated
        with open(skill_json) as f:
            updated_manifest = json.load(f)

        assert "dev_dependencies" in updated_manifest
        assert "test-skill" in updated_manifest["dev_dependencies"]

        del os.environ["SKILLHUB_CACHE_DIR"]


def test_list_installed_empty(tmp_path):
    """Test listing installed skills when none installed."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        import os

        cache_dir = Path.cwd() / ".skillhub-cache"
        os.environ["SKILLHUB_CACHE_DIR"] = str(cache_dir)

        result = runner.invoke(cli, ["list", "--installed"])

        assert result.exit_code == 0
        assert "No skills installed" in result.output

        del os.environ["SKILLHUB_CACHE_DIR"]


def test_list_installed_with_skills(local_registry, sample_skill_dir, tmp_path):
    """Test listing installed skills."""
    # Publish and install a skill
    packager = SkillPackager()
    manifest_path = sample_skill_dir / "skill.json"
    with open(manifest_path) as f:
        manifest_data = json.load(f)

    from skillhub.core.models import SkillManifest

    manifest = SkillManifest(**manifest_data)
    package = packager.package_skill(sample_skill_dir, manifest)

    client = RegistryClient(local_registry_path=local_registry)
    client.publish_skill(package)

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        import os

        cache_dir = Path.cwd() / ".skillhub-cache"
        os.environ["SKILLHUB_CACHE_DIR"] = str(cache_dir)

        # Install
        result = runner.invoke(
            cli, ["install", "test-skill", "--registry", str(local_registry)]
        )
        assert result.exit_code == 0

        # List
        result = runner.invoke(cli, ["list", "--installed"])

        assert result.exit_code == 0
        assert "test-skill" in result.output
        assert "v0.1.0" in result.output
        assert "A test skill" in result.output

        del os.environ["SKILLHUB_CACHE_DIR"]


def test_cache_manager_basic_operations(tmp_path):
    """Test SkillCacheManager basic operations."""
    cache_dir = tmp_path / "cache"
    cache_manager = SkillCacheManager(cache_dir)

    assert cache_manager.get_cache_dir() == cache_dir

    # Test with sample data
    from skillhub.core.models import SkillManifest

    manifest_data = {
        "name": "test-skill",
        "version": "1.0.0",
        "description": "Test",
        "author": "Test",
        "capabilities": [],
        "main_module": "main.py",
        "license": "MIT",
    }
    manifest = SkillManifest(**manifest_data)

    files = {
        "skill.json": json.dumps(manifest_data).encode(),
        "main.py": b"def test(): pass",
    }

    # Cache skill
    install_path = cache_manager.cache_skill("test-skill", "1.0.0", manifest, files)
    assert install_path.exists()
    assert (install_path / "skill.json").exists()
    assert (install_path / "main.py").exists()

    # Get cached skill
    cached = cache_manager.get_cached_skill("test-skill", "1.0.0")
    assert cached is not None
    assert cached.name == "test-skill"
    assert cached.version == "1.0.0"

    # List installed
    installed = cache_manager.list_installed()
    assert len(installed) == 1
    assert installed[0].name == "test-skill"

    # Check existence
    assert cache_manager.skill_exists("test-skill", "1.0.0")
    assert not cache_manager.skill_exists("other-skill", "1.0.0")

    # Remove skill
    assert cache_manager.remove_skill("test-skill", "1.0.0")
    assert not cache_manager.skill_exists("test-skill", "1.0.0")


def test_registry_search_methods(local_registry, sample_skill_dir):
    """Test registry search functionality."""
    # Publish multiple skills
    packager = SkillPackager()

    # First skill
    manifest_path = sample_skill_dir / "skill.json"
    with open(manifest_path) as f:
        manifest_data = json.load(f)

    from skillhub.core.models import SkillManifest

    manifest = SkillManifest(**manifest_data)
    package = packager.package_skill(sample_skill_dir, manifest)

    client = RegistryClient(local_registry_path=local_registry)
    client.publish_skill(package)

    # Search by name
    results = client.search_skills(query="test")
    assert len(results) > 0
    assert any(r.skill_name == "test-skill" for r in results)

    # Search by non-existent query
    results = client.search_skills(query="nonexistent")
    assert len(results) == 0

    # Test limit
    results = client.search_skills(limit=1)
    assert len(results) <= 1


def test_download_skill_package(local_registry, sample_skill_dir):
    """Test downloading skill package from registry."""
    # Publish a skill
    packager = SkillPackager()
    manifest_path = sample_skill_dir / "skill.json"
    with open(manifest_path) as f:
        manifest_data = json.load(f)

    from skillhub.core.models import SkillManifest

    manifest = SkillManifest(**manifest_data)
    package = packager.package_skill(sample_skill_dir, manifest)

    client = RegistryClient(local_registry_path=local_registry)
    client.publish_skill(package)

    # Download the package
    downloaded = client.download_skill_package("test-skill", "0.1.0")
    assert downloaded is not None
    assert downloaded.manifest.name == "test-skill"
    assert downloaded.manifest.version == "0.1.0"
    assert len(downloaded.source_files) > 0

    # Test non-existent skill
    downloaded = client.download_skill_package("nonexistent", "1.0.0")
    assert downloaded is None
