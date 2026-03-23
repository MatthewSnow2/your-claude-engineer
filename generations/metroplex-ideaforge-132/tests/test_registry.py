"""Tests for registry client."""

import json

import pytest

from skillhub.core.models import SkillManifest
from skillhub.core.packaging import SkillPackager
from skillhub.core.registry import RegistryClient


def test_registry_client_initialization(local_registry):
    """Test registry client initialization."""
    client = RegistryClient(local_registry_path=local_registry)
    assert client.local_registry_path == local_registry

    # Check index was created
    index_file = local_registry / "index.json"
    assert index_file.exists()


def test_publish_skill_to_local_registry(sample_skill_dir, sample_manifest_data, local_registry):
    """Test publishing skill to local registry."""
    manifest = SkillManifest(**sample_manifest_data)
    packager = SkillPackager()
    package = packager.package_skill(sample_skill_dir, manifest)

    client = RegistryClient(local_registry_path=local_registry)
    entry = client.publish_skill(package)

    assert entry.skill_name == "test-skill"
    assert entry.latest_version == "0.1.0"
    assert "0.1.0" in entry.versions

    # Check files were saved
    skill_dir = local_registry / "test-skill" / "0.1.0"
    assert skill_dir.exists()
    assert (skill_dir / "skill.json").exists()


def test_publish_skill_with_namespace(sample_skill_dir, sample_manifest_data, local_registry):
    """Test publishing skill with namespace."""
    manifest = SkillManifest(**sample_manifest_data)
    packager = SkillPackager()
    package = packager.package_skill(sample_skill_dir, manifest)

    client = RegistryClient(local_registry_path=local_registry)
    entry = client.publish_skill(package, namespace="myorg", private=True)

    assert entry.namespace == "myorg"
    assert entry.skill_name == "test-skill"

    # Check files were saved in namespace directory
    skill_dir = local_registry / "myorg" / "test-skill" / "0.1.0"
    assert skill_dir.exists()


def test_publish_multiple_versions(sample_skill_dir, sample_manifest_data, local_registry):
    """Test publishing multiple versions of same skill."""
    packager = SkillPackager()
    client = RegistryClient(local_registry_path=local_registry)

    # Publish v0.1.0
    manifest1 = SkillManifest(**sample_manifest_data)
    package1 = packager.package_skill(sample_skill_dir, manifest1)
    entry1 = client.publish_skill(package1)

    assert "0.1.0" in entry1.versions
    assert entry1.latest_version == "0.1.0"

    # Publish v0.2.0
    sample_manifest_data["version"] = "0.2.0"
    manifest2 = SkillManifest(**sample_manifest_data)
    package2 = packager.package_skill(sample_skill_dir, manifest2)
    entry2 = client.publish_skill(package2)

    assert "0.1.0" in entry2.versions
    assert "0.2.0" in entry2.versions
    assert entry2.latest_version == "0.2.0"


def test_get_skill_from_registry(sample_skill_dir, sample_manifest_data, local_registry):
    """Test retrieving skill from registry."""
    manifest = SkillManifest(**sample_manifest_data)
    packager = SkillPackager()
    package = packager.package_skill(sample_skill_dir, manifest)

    client = RegistryClient(local_registry_path=local_registry)
    client.publish_skill(package)

    # Retrieve skill
    entry = client.get_skill("test-skill")
    assert entry is not None
    assert entry.skill_name == "test-skill"
    assert entry.latest_version == "0.1.0"


def test_get_skill_with_namespace(sample_skill_dir, sample_manifest_data, local_registry):
    """Test retrieving skill with namespace."""
    manifest = SkillManifest(**sample_manifest_data)
    packager = SkillPackager()
    package = packager.package_skill(sample_skill_dir, manifest)

    client = RegistryClient(local_registry_path=local_registry)
    client.publish_skill(package, namespace="myorg")

    # Retrieve with namespace
    entry = client.get_skill("test-skill", namespace="myorg")
    assert entry is not None
    assert entry.namespace == "myorg"


def test_get_nonexistent_skill(local_registry):
    """Test retrieving non-existent skill."""
    client = RegistryClient(local_registry_path=local_registry)
    entry = client.get_skill("nonexistent-skill")
    assert entry is None


def test_check_skill_exists(sample_skill_dir, sample_manifest_data, local_registry):
    """Test checking if skill version exists."""
    manifest = SkillManifest(**sample_manifest_data)
    packager = SkillPackager()
    package = packager.package_skill(sample_skill_dir, manifest)

    client = RegistryClient(local_registry_path=local_registry)
    client.publish_skill(package)

    # Check existing version
    assert client.check_skill_exists("test-skill", "0.1.0") is True

    # Check non-existent version
    assert client.check_skill_exists("test-skill", "0.2.0") is False

    # Check non-existent skill
    assert client.check_skill_exists("nonexistent", "0.1.0") is False


def test_registry_index_persistence(sample_skill_dir, sample_manifest_data, local_registry):
    """Test registry index persists correctly."""
    manifest = SkillManifest(**sample_manifest_data)
    packager = SkillPackager()
    package = packager.package_skill(sample_skill_dir, manifest)

    # Publish with first client
    client1 = RegistryClient(local_registry_path=local_registry)
    client1.publish_skill(package)

    # Create new client and verify data persists
    client2 = RegistryClient(local_registry_path=local_registry)
    entry = client2.get_skill("test-skill")
    assert entry is not None
    assert entry.skill_name == "test-skill"
