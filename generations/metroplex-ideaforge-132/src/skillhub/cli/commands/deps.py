"""Dependency management commands."""

import json
import os
from pathlib import Path
from typing import Optional

import click

from skillhub.core.cache import SkillCacheManager
from skillhub.core.dependency_resolver import DependencyResolver
from skillhub.core.models import SkillManifest
from skillhub.core.registry import RegistryClient


def load_skill_manifest() -> Optional[SkillManifest]:
    """Load skill.json from current directory."""
    skill_json = Path.cwd() / "skill.json"
    if not skill_json.exists():
        click.echo("Error: No skill.json found in current directory")
        return None

    try:
        with open(skill_json) as f:
            manifest_data = json.load(f)
        return SkillManifest(**manifest_data)
    except (ValueError, OSError) as e:
        click.echo(f"Error loading skill.json: {e}")
        return None


def get_registry_and_cache(registry_url: Optional[str] = None):
    """Initialize registry client and cache manager."""
    # Determine registry
    local_registry = None

    if registry_url:
        registry_path = Path(registry_url)
        if registry_path.exists() or not registry_url.startswith("http"):
            local_registry = registry_path
            registry_url = None
    elif not os.getenv("SKILLHUB_REGISTRY_URL"):
        # Use local registry for testing
        local_registry_dir = Path.home() / ".skillhub" / "registry"
        if local_registry_dir.exists():
            local_registry = local_registry_dir

    registry = RegistryClient(registry_url=registry_url, local_registry_path=local_registry)
    cache = SkillCacheManager()

    return registry, cache


@click.group()
def deps():
    """Manage skill dependencies."""
    pass


@deps.command()
@click.option("--dev", is_flag=True, help="Include dev dependencies")
@click.option(
    "--registry",
    default=None,
    help="Custom registry URL (defaults to SKILLHUB_REGISTRY_URL or local)",
)
def install(dev: bool, registry: str):
    """Resolve and install all skill dependencies from skill.json."""
    # Load manifest
    manifest = load_skill_manifest()
    if not manifest:
        return

    # Get registry and cache
    reg, cache = get_registry_and_cache(registry)

    # Resolve dependencies
    click.echo("Resolving dependencies...")
    resolver = DependencyResolver(reg, cache)

    try:
        resolved = resolver.resolve_dependencies(manifest, include_dev=dev)
    except (ValueError, OSError) as e:
        click.echo(f"Error resolving dependencies: {e}")
        return

    # Check for conflicts
    if resolved.conflicts:
        click.echo("\nConflicts detected:")
        for conflict in resolved.conflicts:
            click.echo(f"\n  {conflict.skill_name}:")
            click.echo(f"    Required by:")
            for requester, constraint in conflict.required_by.items():
                click.echo(f"      - {requester}: {constraint}")
            if conflict.available_versions:
                click.echo(f"    Available versions: {', '.join(conflict.available_versions)}")
            else:
                click.echo(f"    Skill not found in registry")
            if conflict.resolved_version:
                click.echo(f"    Attempted resolution: {conflict.resolved_version}")
        click.echo("\nCannot proceed with installation due to conflicts.")
        return

    if not resolved.dependencies:
        click.echo("No dependencies to install.")
        return

    # Display resolution plan
    click.echo(f"\nResolved {len(resolved.dependencies)} dependencies:")
    for dep in resolved.dependencies:
        dev_marker = " (dev)" if dep.is_dev else ""
        click.echo(f"  {dep.name}@{dep.version}{dev_marker}")

    # Install in resolution order
    click.echo("\nInstalling dependencies...")
    for skill_name in resolved.resolution_order:
        # Find the resolved dependency
        dep = next((d for d in resolved.dependencies if d.name == skill_name), None)
        if not dep:
            continue

        # Check if already installed
        if cache.skill_exists(skill_name, dep.version):
            click.echo(f"  ✓ {skill_name}@{dep.version} (already installed)")
            continue

        # Download and install
        try:
            click.echo(f"  Installing {skill_name}@{dep.version}...")
            package = reg.download_skill_package(skill_name, dep.version)

            if not package:
                click.echo(f"    Error: Failed to download {skill_name}@{dep.version}")
                continue

            cache.cache_skill(skill_name, dep.version, package.manifest, package.source_files)
            click.echo(f"  ✓ {skill_name}@{dep.version}")

        except (ValueError, OSError) as e:
            click.echo(f"    Error installing {skill_name}@{dep.version}: {e}")
            continue

    click.echo("\nDependency installation complete!")


@deps.command()
@click.option("--dev", is_flag=True, help="Include dev dependencies")
@click.option(
    "--registry",
    default=None,
    help="Custom registry URL (defaults to SKILLHUB_REGISTRY_URL or local)",
)
def tree(dev: bool, registry: str):
    """Show dependency graph with version constraints."""
    # Load manifest
    manifest = load_skill_manifest()
    if not manifest:
        return

    # Get registry and cache
    reg, cache = get_registry_and_cache(registry)

    # Resolve dependencies
    resolver = DependencyResolver(reg, cache)

    try:
        resolved = resolver.resolve_dependencies(manifest, include_dev=dev)
    except (ValueError, OSError) as e:
        click.echo(f"Error resolving dependencies: {e}")
        return

    # Display tree
    click.echo(f"\n{manifest.name}@{manifest.version}")

    if not resolved.dependencies:
        click.echo("  (no dependencies)")
        return

    # Build tree structure
    dep_map = {d.name: d for d in resolved.dependencies}

    def print_tree(skill_name: str, version: str, deps: dict, indent: str, printed: set):
        """Recursively print dependency tree."""
        for i, (dep_name, constraint) in enumerate(deps.items()):
            is_last = i == len(deps) - 1
            prefix = "└── " if is_last else "├── "
            continuation = "    " if is_last else "│   "

            dep_info = dep_map.get(dep_name)
            if dep_info:
                dev_marker = " (dev)" if dep_info.is_dev else ""
                click.echo(f"{indent}{prefix}{dep_name}@{dep_info.version} ({constraint}){dev_marker}")

                # Print sub-dependencies if not already printed (avoid cycles)
                dep_key = f"{dep_name}@{dep_info.version}"
                if dep_key not in printed and dep_info.dependencies:
                    printed.add(dep_key)
                    print_tree(dep_name, dep_info.version, dep_info.dependencies,
                             indent + continuation, printed)
            else:
                click.echo(f"{indent}{prefix}{dep_name} ({constraint}) - NOT RESOLVED")

    printed_deps = set()
    print_tree(manifest.name, manifest.version, manifest.dependencies, "", printed_deps)

    if dev and manifest.dev_dependencies:
        click.echo("\nDevelopment dependencies:")
        print_tree(manifest.name, manifest.version, manifest.dev_dependencies, "", printed_deps)

    # Show conflicts if any
    if resolved.conflicts:
        click.echo("\nConflicts:")
        for conflict in resolved.conflicts:
            click.echo(f"  ⚠ {conflict.skill_name}")
            for requester, constraint in conflict.required_by.items():
                click.echo(f"    - {requester} requires {constraint}")


@deps.command()
@click.option("--dev", is_flag=True, help="Include dev dependencies")
@click.option(
    "--registry",
    default=None,
    help="Custom registry URL (defaults to SKILLHUB_REGISTRY_URL or local)",
)
def lock(dev: bool, registry: str):
    """Generate skillhub.lock with exact dependency versions."""
    # Load manifest
    manifest = load_skill_manifest()
    if not manifest:
        return

    # Get registry and cache
    reg, cache = get_registry_and_cache(registry)

    # Resolve dependencies
    click.echo("Resolving dependencies...")
    resolver = DependencyResolver(reg, cache)

    try:
        resolved = resolver.resolve_dependencies(manifest, include_dev=dev)
    except (ValueError, OSError) as e:
        click.echo(f"Error resolving dependencies: {e}")
        return

    # Check for conflicts
    if resolved.conflicts:
        click.echo("\nError: Cannot generate lock file due to conflicts:")
        for conflict in resolved.conflicts:
            click.echo(f"  - {conflict.skill_name}")
            for requester, constraint in conflict.required_by.items():
                click.echo(f"    Required by {requester}: {constraint}")
        return

    # Generate lock data
    lock_data = resolver.generate_lock_data(resolved)

    # Write lock file
    lock_file = Path.cwd() / "skillhub.lock"
    with open(lock_file, "w") as f:
        json.dump(lock_data, f, indent=2)

    click.echo(f"\nGenerated skillhub.lock with {len(resolved.dependencies)} dependencies")
    click.echo(f"Resolution order: {' -> '.join(resolved.resolution_order)}")


@deps.command()
@click.option("--check", is_flag=True, help="Only check for updates without installing")
@click.option(
    "--registry",
    default=None,
    help="Custom registry URL (defaults to SKILLHUB_REGISTRY_URL or local)",
)
def update(check: bool, registry: str):
    """Update dependencies or check for available updates."""
    # Load manifest
    manifest = load_skill_manifest()
    if not manifest:
        return

    # Get registry and cache
    reg, cache = get_registry_and_cache(registry)

    # Check each dependency for updates
    updates_available = []

    all_deps = {**manifest.dependencies}
    if manifest.dev_dependencies:
        all_deps.update(manifest.dev_dependencies)

    if not all_deps:
        click.echo("No dependencies defined in skill.json")
        return

    click.echo("Checking for updates...")

    for dep_name, constraint in all_deps.items():
        # Get installed version
        cached = cache.get_cached_skill(dep_name)
        if not cached:
            click.echo(f"  {dep_name}: Not installed")
            continue

        installed_version = cached.version

        # Get latest version from registry
        try:
            entry = reg.get_skill(dep_name)
            if not entry:
                click.echo(f"  {dep_name}: Not found in registry")
                continue

            latest_version = entry.latest_version

            # Check if update available
            resolver = DependencyResolver(reg, cache)
            if resolver.compare_versions(latest_version, installed_version) > 0:
                # Check if latest satisfies constraint
                if resolver.version_satisfies(latest_version, constraint):
                    updates_available.append((dep_name, installed_version, latest_version, constraint))
                    click.echo(f"  {dep_name}: {installed_version} -> {latest_version} (compatible)")
                else:
                    click.echo(f"  {dep_name}: {installed_version} (latest: {latest_version}, but incompatible with {constraint})")
            else:
                click.echo(f"  {dep_name}: {installed_version} (up to date)")

        except (ValueError, OSError) as e:
            click.echo(f"  {dep_name}: Error checking updates: {e}")
            continue

    # Display summary
    if updates_available:
        click.echo(f"\n{len(updates_available)} update(s) available:")
        for dep_name, old_ver, new_ver, constraint in updates_available:
            click.echo(f"  {dep_name}: {old_ver} -> {new_ver}")

        if check:
            click.echo("\nRun 'skillhub deps update' to install updates")
        else:
            # Install updates
            click.echo("\nInstalling updates...")
            for dep_name, old_ver, new_ver, constraint in updates_available:
                try:
                    click.echo(f"  Updating {dep_name}...")
                    package = reg.download_skill_package(dep_name, new_ver)

                    if not package:
                        click.echo(f"    Error: Failed to download {dep_name}@{new_ver}")
                        continue

                    cache.cache_skill(dep_name, new_ver, package.manifest, package.source_files)
                    click.echo(f"  ✓ {dep_name}@{new_ver}")

                except (ValueError, OSError) as e:
                    click.echo(f"    Error updating {dep_name}: {e}")
                    continue

            click.echo("\nUpdate complete!")
    else:
        click.echo("\nAll dependencies are up to date!")
