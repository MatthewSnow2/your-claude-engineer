"""Tests for dependency resolution."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner

from skillhub.cli.commands.deps import deps
from skillhub.core.cache import SkillCacheManager
from skillhub.core.dependency_resolver import DependencyResolver, ResolvedDependency
from skillhub.core.models import RegistryEntry, SkillManifest, SkillPackage
from skillhub.core.registry import RegistryClient


@pytest.fixture
def sample_manifest_with_deps():
    """Return sample manifest with dependencies."""
    return {
        "name": "main-skill",
        "version": "1.0.0",
        "description": "Main skill with dependencies",
        "author": "Test Author",
        "agent_skills_version": "1.0.0",
        "capabilities": [
            {
                "name": "test_capability",
                "description": "Test capability",
                "input_schema": {"type": "object", "properties": {"input": {"type": "string"}}},
                "output_schema": {"type": "object", "properties": {"result": {"type": "string"}}},
                "required_permissions": [],
            }
        ],
        "dependencies": {
            "dep-a": "^1.0.0",
            "dep-b": "~2.1.0",
        },
        "dev_dependencies": {
            "dev-dep": ">=1.0.0,<2.0.0",
        },
        "main_module": "main.py",
        "mcp_tools": [],
        "license": "MIT",
        "keywords": ["test"],
    }


@pytest.fixture
def registry_with_deps(local_registry):
    """Create a registry with test dependencies."""
    registry = RegistryClient(local_registry_path=local_registry)

    # Helper to create skill packages
    def create_skill(name: str, version: str, deps: dict = None):
        manifest_data = {
            "name": name,
            "version": version,
            "description": f"Test skill {name}",
            "author": "Test",
            "agent_skills_version": "1.0.0",
            "capabilities": [
                {
                    "name": "test",
                    "description": "Test",
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                }
            ],
            "dependencies": deps or {},
            "main_module": "main.py",
            "license": "MIT",
        }
        manifest = SkillManifest(**manifest_data)
        package = SkillPackage(
            manifest=manifest,
            source_files={"skill.json": json.dumps(manifest_data).encode()},
            package_size=100,
            checksum="abc123",
            created_at=datetime.now(timezone.utc),
        )
        return package

    # Publish test skills
    registry.publish_skill(create_skill("dep-a", "1.0.0"))
    registry.publish_skill(create_skill("dep-a", "1.1.0"))
    registry.publish_skill(create_skill("dep-a", "1.2.0"))
    registry.publish_skill(create_skill("dep-a", "2.0.0"))

    registry.publish_skill(create_skill("dep-b", "2.1.0"))
    registry.publish_skill(create_skill("dep-b", "2.1.5"))
    registry.publish_skill(create_skill("dep-b", "2.2.0"))

    registry.publish_skill(create_skill("dev-dep", "1.0.0"))
    registry.publish_skill(create_skill("dev-dep", "1.5.0"))

    # Skill with sub-dependencies
    registry.publish_skill(create_skill("dep-c", "1.0.0", {"dep-d": "^1.0.0"}))
    registry.publish_skill(create_skill("dep-d", "1.0.0"))
    registry.publish_skill(create_skill("dep-d", "1.1.0"))

    return registry


class TestVersionParsing:
    """Tests for version constraint parsing."""

    def test_parse_version_constraint_exact(self):
        """Test parsing exact version constraint."""
        resolver = DependencyResolver(None, None)
        operator, version = resolver.parse_version_constraint("1.2.3")
        assert operator == "exact"
        assert version == "1.2.3"

    def test_parse_version_constraint_caret(self):
        """Test parsing caret constraint."""
        resolver = DependencyResolver(None, None)
        operator, version = resolver.parse_version_constraint("^1.2.0")
        assert operator == "caret"
        assert version == "1.2.0"

    def test_parse_version_constraint_tilde(self):
        """Test parsing tilde constraint."""
        resolver = DependencyResolver(None, None)
        operator, version = resolver.parse_version_constraint("~1.2.0")
        assert operator == "tilde"
        assert version == "1.2.0"

    def test_parse_version_constraint_range(self):
        """Test parsing range constraint."""
        resolver = DependencyResolver(None, None)
        operator, version = resolver.parse_version_constraint(">=1.0.0,<2.0.0")
        assert operator == "range"
        assert version == ">=1.0.0,<2.0.0"

    def test_parse_version_constraint_wildcard(self):
        """Test parsing wildcard constraint."""
        resolver = DependencyResolver(None, None)
        operator, version = resolver.parse_version_constraint("*")
        assert operator == "any"
        assert version == ""

    def test_parse_version_constraint_latest(self):
        """Test parsing 'latest' constraint."""
        resolver = DependencyResolver(None, None)
        operator, version = resolver.parse_version_constraint("latest")
        assert operator == "any"


class TestVersionSatisfies:
    """Tests for version satisfaction checking."""

    def test_version_satisfies_exact(self):
        """Test exact version matching."""
        resolver = DependencyResolver(None, None)
        assert resolver.version_satisfies("1.2.3", "1.2.3")
        assert not resolver.version_satisfies("1.2.4", "1.2.3")

    def test_version_satisfies_caret(self):
        """Test caret version matching."""
        resolver = DependencyResolver(None, None)
        # ^1.2.0 allows 1.2.0 to 1.x.x
        assert resolver.version_satisfies("1.2.0", "^1.2.0")
        assert resolver.version_satisfies("1.2.5", "^1.2.0")
        assert resolver.version_satisfies("1.9.9", "^1.2.0")
        assert not resolver.version_satisfies("2.0.0", "^1.2.0")
        assert not resolver.version_satisfies("1.1.9", "^1.2.0")

    def test_version_satisfies_caret_zero_major(self):
        """Test caret with zero major version."""
        resolver = DependencyResolver(None, None)
        # ^0.2.3 allows 0.2.3 to 0.2.x
        assert resolver.version_satisfies("0.2.3", "^0.2.3")
        assert resolver.version_satisfies("0.2.5", "^0.2.3")
        assert not resolver.version_satisfies("0.3.0", "^0.2.3")
        assert not resolver.version_satisfies("1.0.0", "^0.2.3")

    def test_version_satisfies_tilde(self):
        """Test tilde version matching."""
        resolver = DependencyResolver(None, None)
        # ~1.2.3 allows 1.2.3 to 1.2.x
        assert resolver.version_satisfies("1.2.3", "~1.2.3")
        assert resolver.version_satisfies("1.2.9", "~1.2.3")
        assert not resolver.version_satisfies("1.3.0", "~1.2.3")
        assert not resolver.version_satisfies("2.0.0", "~1.2.3")

    def test_version_satisfies_range(self):
        """Test range version matching."""
        resolver = DependencyResolver(None, None)
        assert resolver.version_satisfies("1.5.0", ">=1.0.0,<2.0.0")
        assert resolver.version_satisfies("1.0.0", ">=1.0.0,<2.0.0")
        assert not resolver.version_satisfies("0.9.9", ">=1.0.0,<2.0.0")
        assert not resolver.version_satisfies("2.0.0", ">=1.0.0,<2.0.0")

    def test_version_satisfies_wildcard(self):
        """Test wildcard matching."""
        resolver = DependencyResolver(None, None)
        assert resolver.version_satisfies("1.2.3", "*")
        assert resolver.version_satisfies("0.0.1", "latest")


class TestCompareVersions:
    """Tests for version comparison."""

    def test_compare_versions_equal(self):
        """Test comparing equal versions."""
        resolver = DependencyResolver(None, None)
        assert resolver.compare_versions("1.2.3", "1.2.3") == 0

    def test_compare_versions_less(self):
        """Test comparing less version."""
        resolver = DependencyResolver(None, None)
        assert resolver.compare_versions("1.2.3", "1.2.4") == -1
        assert resolver.compare_versions("1.2.3", "1.3.0") == -1
        assert resolver.compare_versions("1.2.3", "2.0.0") == -1

    def test_compare_versions_greater(self):
        """Test comparing greater version."""
        resolver = DependencyResolver(None, None)
        assert resolver.compare_versions("1.2.4", "1.2.3") == 1
        assert resolver.compare_versions("1.3.0", "1.2.3") == 1
        assert resolver.compare_versions("2.0.0", "1.2.3") == 1


class TestFindBestVersion:
    """Tests for finding best matching version."""

    def test_find_best_version_exact(self):
        """Test finding exact version."""
        resolver = DependencyResolver(None, None)
        versions = ["1.0.0", "1.1.0", "1.2.0", "2.0.0"]
        best = resolver.find_best_version(versions, "1.1.0")
        assert best == "1.1.0"

    def test_find_best_version_caret(self):
        """Test finding best version with caret."""
        resolver = DependencyResolver(None, None)
        versions = ["1.0.0", "1.1.0", "1.2.0", "2.0.0"]
        best = resolver.find_best_version(versions, "^1.0.0")
        assert best == "1.2.0"  # Highest matching 1.x.x

    def test_find_best_version_tilde(self):
        """Test finding best version with tilde."""
        resolver = DependencyResolver(None, None)
        versions = ["2.1.0", "2.1.5", "2.2.0", "3.0.0"]
        best = resolver.find_best_version(versions, "~2.1.0")
        assert best == "2.1.5"  # Highest matching 2.1.x

    def test_find_best_version_no_match(self):
        """Test when no version matches."""
        resolver = DependencyResolver(None, None)
        versions = ["1.0.0", "1.1.0", "1.2.0"]
        best = resolver.find_best_version(versions, "^2.0.0")
        assert best is None


class TestResolveSimpleDependencies:
    """Tests for simple dependency resolution."""

    def test_resolve_simple_dependencies(self, registry_with_deps, tmp_path):
        """Test resolving simple dependencies."""
        cache = SkillCacheManager(cache_dir=tmp_path)
        resolver = DependencyResolver(registry_with_deps, cache)

        manifest_data = {
            "name": "test-skill",
            "version": "1.0.0",
            "description": "Test",
            "author": "Test",
            "agent_skills_version": "1.0.0",
            "capabilities": [
                {
                    "name": "test",
                    "description": "Test",
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                }
            ],
            "dependencies": {"dep-a": "^1.0.0"},
            "main_module": "main.py",
            "license": "MIT",
        }
        manifest = SkillManifest(**manifest_data)

        resolved = resolver.resolve_dependencies(manifest, include_dev=False)

        assert len(resolved.dependencies) == 1
        assert resolved.dependencies[0].name == "dep-a"
        assert resolved.dependencies[0].version == "1.2.0"  # Latest 1.x.x
        assert len(resolved.conflicts) == 0
        assert "dep-a" in resolved.resolution_order

    def test_resolve_multiple_dependencies(self, registry_with_deps, tmp_path):
        """Test resolving multiple dependencies."""
        cache = SkillCacheManager(cache_dir=tmp_path)
        resolver = DependencyResolver(registry_with_deps, cache)

        manifest_data = {
            "name": "test-skill",
            "version": "1.0.0",
            "description": "Test",
            "author": "Test",
            "agent_skills_version": "1.0.0",
            "capabilities": [
                {
                    "name": "test",
                    "description": "Test",
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                }
            ],
            "dependencies": {"dep-a": "^1.0.0", "dep-b": "~2.1.0"},
            "main_module": "main.py",
            "license": "MIT",
        }
        manifest = SkillManifest(**manifest_data)

        resolved = resolver.resolve_dependencies(manifest, include_dev=False)

        assert len(resolved.dependencies) == 2
        dep_names = {d.name for d in resolved.dependencies}
        assert "dep-a" in dep_names
        assert "dep-b" in dep_names
        assert len(resolved.conflicts) == 0

    def test_resolve_nested_dependencies(self, registry_with_deps, tmp_path):
        """Test resolving nested dependencies."""
        cache = SkillCacheManager(cache_dir=tmp_path)
        resolver = DependencyResolver(registry_with_deps, cache)

        manifest_data = {
            "name": "test-skill",
            "version": "1.0.0",
            "description": "Test",
            "author": "Test",
            "agent_skills_version": "1.0.0",
            "capabilities": [
                {
                    "name": "test",
                    "description": "Test",
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                }
            ],
            "dependencies": {"dep-c": "^1.0.0"},
            "main_module": "main.py",
            "license": "MIT",
        }
        manifest = SkillManifest(**manifest_data)

        resolved = resolver.resolve_dependencies(manifest, include_dev=False)

        # Should resolve both dep-c and its dependency dep-d
        assert len(resolved.dependencies) == 2
        dep_names = {d.name for d in resolved.dependencies}
        assert "dep-c" in dep_names
        assert "dep-d" in dep_names
        assert len(resolved.conflicts) == 0

        # dep-d should come before dep-c in resolution order
        assert resolved.resolution_order.index("dep-d") < resolved.resolution_order.index("dep-c")


class TestDependencyConflicts:
    """Tests for dependency conflict detection."""

    def test_detect_conflict_no_matching_version(self, registry_with_deps, tmp_path):
        """Test detecting conflict when no matching version exists."""
        cache = SkillCacheManager(cache_dir=tmp_path)
        resolver = DependencyResolver(registry_with_deps, cache)

        manifest_data = {
            "name": "test-skill",
            "version": "1.0.0",
            "description": "Test",
            "author": "Test",
            "agent_skills_version": "1.0.0",
            "capabilities": [
                {
                    "name": "test",
                    "description": "Test",
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                }
            ],
            "dependencies": {"dep-a": "^5.0.0"},  # Version doesn't exist
            "main_module": "main.py",
            "license": "MIT",
        }
        manifest = SkillManifest(**manifest_data)

        resolved = resolver.resolve_dependencies(manifest, include_dev=False)

        assert len(resolved.conflicts) > 0
        assert any(c.skill_name == "dep-a" for c in resolved.conflicts)

    def test_detect_nonexistent_skill(self, registry_with_deps, tmp_path):
        """Test detecting conflict for nonexistent skill."""
        cache = SkillCacheManager(cache_dir=tmp_path)
        resolver = DependencyResolver(registry_with_deps, cache)

        manifest_data = {
            "name": "test-skill",
            "version": "1.0.0",
            "description": "Test",
            "author": "Test",
            "agent_skills_version": "1.0.0",
            "capabilities": [
                {
                    "name": "test",
                    "description": "Test",
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                }
            ],
            "dependencies": {"nonexistent-skill": "^1.0.0"},
            "main_module": "main.py",
            "license": "MIT",
        }
        manifest = SkillManifest(**manifest_data)

        resolved = resolver.resolve_dependencies(manifest, include_dev=False)

        assert len(resolved.conflicts) > 0
        conflict = next(c for c in resolved.conflicts if c.skill_name == "nonexistent-skill")
        assert len(conflict.available_versions) == 0


class TestGenerateLockFile:
    """Tests for lock file generation."""

    def test_generate_lock_data(self, registry_with_deps, tmp_path):
        """Test generating lock file data."""
        cache = SkillCacheManager(cache_dir=tmp_path)
        resolver = DependencyResolver(registry_with_deps, cache)

        manifest_data = {
            "name": "test-skill",
            "version": "1.0.0",
            "description": "Test",
            "author": "Test",
            "agent_skills_version": "1.0.0",
            "capabilities": [
                {
                    "name": "test",
                    "description": "Test",
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                }
            ],
            "dependencies": {"dep-a": "^1.0.0"},
            "main_module": "main.py",
            "license": "MIT",
        }
        manifest = SkillManifest(**manifest_data)

        resolved = resolver.resolve_dependencies(manifest, include_dev=False)
        lock_data = resolver.generate_lock_data(resolved)

        assert "version" in lock_data
        assert "generated_at" in lock_data
        assert "dependencies" in lock_data
        assert "resolution_order" in lock_data

        assert "dep-a" in lock_data["dependencies"]
        assert lock_data["dependencies"]["dep-a"]["version"] == "1.2.0"
        assert lock_data["dependencies"]["dep-a"]["constraint"] == "^1.0.0"


class TestCliCommands:
    """Tests for CLI commands."""

    def test_deps_install_command(self, registry_with_deps, tmp_path, sample_manifest_with_deps):
        """Test 'skillhub deps install' command."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create skill.json
            skill_json = Path.cwd() / "skill.json"
            skill_json.write_text(json.dumps(sample_manifest_with_deps, indent=2))

            # Run install command
            result = runner.invoke(deps, ["install", "--registry", str(registry_with_deps.local_registry_path)])

            assert result.exit_code == 0
            assert "Resolving dependencies" in result.output
            assert "dep-a" in result.output
            assert "dep-b" in result.output

    def test_deps_tree_command(self, registry_with_deps, tmp_path, sample_manifest_with_deps):
        """Test 'skillhub deps tree' command."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create skill.json
            skill_json = Path.cwd() / "skill.json"
            skill_json.write_text(json.dumps(sample_manifest_with_deps, indent=2))

            # Run tree command
            result = runner.invoke(deps, ["tree", "--registry", str(registry_with_deps.local_registry_path)])

            assert result.exit_code == 0
            assert "main-skill" in result.output
            assert "dep-a" in result.output
            assert "dep-b" in result.output

    def test_deps_lock_command(self, registry_with_deps, tmp_path, sample_manifest_with_deps):
        """Test 'skillhub deps lock' command."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create skill.json
            skill_json = Path.cwd() / "skill.json"
            skill_json.write_text(json.dumps(sample_manifest_with_deps, indent=2))

            # Run lock command
            result = runner.invoke(deps, ["lock", "--registry", str(registry_with_deps.local_registry_path)])

            assert result.exit_code == 0
            assert "Generated skillhub.lock" in result.output

            # Verify lock file created
            lock_file = Path.cwd() / "skillhub.lock"
            assert lock_file.exists()

            # Verify lock file content
            lock_data = json.loads(lock_file.read_text())
            assert "version" in lock_data
            assert "dependencies" in lock_data
            assert "dep-a" in lock_data["dependencies"]
            assert "dep-b" in lock_data["dependencies"]

    def test_deps_update_check_command(self, registry_with_deps, tmp_path):
        """Test 'skillhub deps update --check' command."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create skill.json with older version
            manifest_data = {
                "name": "test-skill",
                "version": "1.0.0",
                "description": "Test",
                "author": "Test",
                "agent_skills_version": "1.0.0",
                "capabilities": [
                    {
                        "name": "test",
                        "description": "Test",
                        "input_schema": {"type": "object"},
                        "output_schema": {"type": "object"},
                    }
                ],
                "dependencies": {"dep-a": "^1.0.0"},
                "main_module": "main.py",
                "license": "MIT",
            }
            skill_json = Path.cwd() / "skill.json"
            skill_json.write_text(json.dumps(manifest_data, indent=2))

            # Install older version
            cache = SkillCacheManager(cache_dir=tmp_path)
            package = registry_with_deps.download_skill_package("dep-a", "1.0.0")
            cache.cache_skill("dep-a", "1.0.0", package.manifest, package.source_files)

            # Run update check
            result = runner.invoke(
                deps,
                ["update", "--check", "--registry", str(registry_with_deps.local_registry_path)],
            )

            assert result.exit_code == 0
            assert "Checking for updates" in result.output
            # Should show update available from 1.0.0 to 1.2.0

    def test_deps_command_no_skill_json(self, tmp_path):
        """Test deps commands fail gracefully without skill.json."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(deps, ["install"])

            assert result.exit_code == 0
            assert "No skill.json found" in result.output


class TestResolutionOrder:
    """Tests for dependency resolution order."""

    def test_resolution_order_simple(self, registry_with_deps, tmp_path):
        """Test resolution order for simple dependencies."""
        cache = SkillCacheManager(cache_dir=tmp_path)
        resolver = DependencyResolver(registry_with_deps, cache)

        manifest_data = {
            "name": "test-skill",
            "version": "1.0.0",
            "description": "Test",
            "author": "Test",
            "agent_skills_version": "1.0.0",
            "capabilities": [
                {
                    "name": "test",
                    "description": "Test",
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                }
            ],
            "dependencies": {"dep-c": "^1.0.0"},  # dep-c depends on dep-d
            "main_module": "main.py",
            "license": "MIT",
        }
        manifest = SkillManifest(**manifest_data)

        resolved = resolver.resolve_dependencies(manifest, include_dev=False)

        # dep-d must be installed before dep-c
        dep_d_index = resolved.resolution_order.index("dep-d")
        dep_c_index = resolved.resolution_order.index("dep-c")
        assert dep_d_index < dep_c_index
