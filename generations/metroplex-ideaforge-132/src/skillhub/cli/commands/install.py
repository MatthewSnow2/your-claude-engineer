"""Skill installation command."""

import json
import os
from pathlib import Path

import click

from skillhub.core.cache import SkillCacheManager
from skillhub.core.packaging import SkillPackager
from skillhub.core.registry import RegistryClient


def parse_package_spec(spec: str) -> tuple:
    """
    Parse package specification.

    Args:
        spec: Package spec like 'name@version' or 'name'

    Returns:
        Tuple of (name, version or None)
    """
    if not spec or not spec.strip():
        raise ValueError("Package spec cannot be empty")
    if "@" in spec:
        parts = spec.split("@", 1)
        if not parts[0] or not parts[1]:
            raise ValueError("Invalid package spec format")
        return parts[0].strip(), parts[1].strip()
    return spec.strip(), None


@click.command()
@click.argument("package_spec")
@click.option("--save-dev", is_flag=True, help="Add to dev_dependencies in skill.json")
@click.option("--force", is_flag=True, help="Force reinstall if already installed")
@click.option(
    "--registry",
    default=None,
    help="Custom registry URL (defaults to SKILLHUB_REGISTRY_URL or local)",
)
def install(package_spec: str, save_dev: bool, force: bool, registry: str):
    """Install a skill from the registry or local .skillpkg file."""
    # Check if package_spec is a path to .skillpkg file
    if package_spec.endswith(".skillpkg"):
        install_from_file(package_spec, save_dev, force)
        return

    # Parse package specification
    skill_name, version = parse_package_spec(package_spec)

    # Determine registry (local or remote)
    local_registry = None
    registry_url = registry

    # Check if registry is a local path
    if registry:
        registry_path = Path(registry)
        if registry_path.exists() or not registry.startswith("http"):
            # Treat as local registry path
            local_registry = registry_path
            registry_url = None
    elif not os.getenv("SKILLHUB_REGISTRY_URL"):
        # Use local registry for testing if SKILLHUB_REGISTRY_URL not set
        local_registry_dir = Path.home() / ".skillhub" / "registry"
        if local_registry_dir.exists():
            local_registry = local_registry_dir

    # Initialize cache manager
    cache_manager = SkillCacheManager()

    # Check if already installed
    if not force and cache_manager.skill_exists(skill_name, version):
        existing = cache_manager.get_cached_skill(skill_name, version)
        click.echo(
            f"Skill {skill_name}@{existing.version} is already installed at {existing.install_path}"
        )
        click.echo("Use --force to reinstall")
        return

    # Connect to registry
    try:
        client = RegistryClient(registry_url=registry_url, local_registry_path=local_registry)

        # Get skill info
        entry = client.get_skill(skill_name)
        if not entry:
            click.echo(f"Error: Skill '{skill_name}' not found in registry")
            return

        # Determine version to install
        if version is None:
            version = entry.latest_version
            click.echo(f"Installing latest version: {version}")
        elif version not in entry.versions:
            click.echo(f"Error: Version {version} not found")
            click.echo(f"Available versions: {', '.join(entry.versions)}")
            return

        # Download package
        click.echo(f"Downloading {skill_name}@{version}...")
        package = client.download_skill_package(skill_name, version, entry.namespace)

        if not package:
            click.echo(f"Error: Failed to download package")
            return

        # Cache the skill
        click.echo("Installing to local cache...")
        install_path = cache_manager.cache_skill(
            skill_name, version, package.manifest, package.source_files
        )

        click.echo(f"\nSuccessfully installed {skill_name}@{version}")
        click.echo(f"Location: {install_path}")
        click.echo(f"Size: {package.package_size} bytes")

        # Handle dependencies
        if package.manifest.dependencies:
            click.echo(f"\nDependencies: {', '.join(package.manifest.dependencies.keys())}")
            click.echo("Note: Automatic dependency resolution not yet implemented")

        # Update skill.json if --save-dev
        if save_dev:
            update_skill_manifest(skill_name, version, save_dev)

    except (ValueError, OSError) as e:
        click.echo(f"Error installing skill: {e}")
        return


def install_from_file(file_path: str, save_dev: bool, force: bool):
    """Install skill from local .skillpkg file."""
    pkg_path = Path(file_path)

    if not pkg_path.exists():
        click.echo(f"Error: File not found: {file_path}")
        return

    click.echo(f"Installing from {file_path}...")

    try:
        # Extract package to temporary directory
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            packager = SkillPackager()
            manifest = packager.extract_package(pkg_path, temp_path)

            # Initialize cache manager
            cache_manager = SkillCacheManager()

            # Check if already installed
            if not force and cache_manager.skill_exists(manifest.name, manifest.version):
                existing = cache_manager.get_cached_skill(manifest.name, manifest.version)
                click.echo(
                    f"Skill {manifest.name}@{existing.version} is already installed at {existing.install_path}"
                )
                click.echo("Use --force to reinstall")
                return

            # Collect files
            source_files = {}
            for file_path in temp_path.rglob("*"):
                if file_path.is_file() and not file_path.is_symlink():
                    rel_path = file_path.relative_to(temp_path)
                    source_files[str(rel_path)] = file_path.read_bytes()

            # Cache the skill
            click.echo("Installing to local cache...")
            install_path = cache_manager.cache_skill(
                manifest.name, manifest.version, manifest, source_files
            )

            click.echo(f"\nSuccessfully installed {manifest.name}@{manifest.version}")
            click.echo(f"Location: {install_path}")

            # Update skill.json if --save-dev
            if save_dev:
                update_skill_manifest(manifest.name, manifest.version, save_dev)

    except (ValueError, OSError) as e:
        click.echo(f"Error installing from file: {e}")
        return


def update_skill_manifest(skill_name: str, version: str, save_dev: bool):
    """Update current skill.json with new dependency."""
    skill_json = Path.cwd() / "skill.json"

    if not skill_json.exists():
        click.echo("\nNote: No skill.json found in current directory - skipping dependency update")
        return

    try:
        with open(skill_json) as f:
            manifest_data = json.load(f)

        # Add to appropriate dependencies
        if save_dev:
            if "dev_dependencies" not in manifest_data:
                manifest_data["dev_dependencies"] = {}
            manifest_data["dev_dependencies"][skill_name] = f"^{version}"
            click.echo(f"\nAdded {skill_name}@^{version} to dev_dependencies in skill.json")
        else:
            if "dependencies" not in manifest_data:
                manifest_data["dependencies"] = {}
            manifest_data["dependencies"][skill_name] = f"^{version}"
            click.echo(f"\nAdded {skill_name}@^{version} to dependencies in skill.json")

        # Write back
        with open(skill_json, "w") as f:
            json.dump(manifest_data, f, indent=2)

    except (ValueError, OSError) as e:
        click.echo(f"\nWarning: Could not update skill.json: {e}")
