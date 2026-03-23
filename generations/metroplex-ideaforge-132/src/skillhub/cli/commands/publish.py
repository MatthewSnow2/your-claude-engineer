"""Skill publishing command."""

import os
from pathlib import Path

import click

from skillhub.core.packaging import SkillPackager
from skillhub.core.registry import RegistryClient
from skillhub.core.validation import SkillValidator


@click.command()
@click.option("--private", is_flag=True, help="Publish as private skill")
@click.option("--namespace", default=None, help="Namespace for private skills")
@click.option(
    "--registry",
    default=None,
    help="Custom registry URL (defaults to SKILLHUB_REGISTRY_URL or local)",
)
@click.option("--dry-run", is_flag=True, help="Validate and package without publishing")
def publish(private: bool, namespace: str, registry: str, dry_run: bool):
    """Publish skill to MCP registry."""
    skill_dir = Path.cwd()

    # Check for skill.json
    manifest_path = skill_dir / "skill.json"
    if not manifest_path.exists():
        click.echo("Error: skill.json not found in current directory")
        click.echo("Run 'skillhub init <skill-name>' to create a new skill")
        return

    click.echo("Validating skill manifest...")

    # Validate skill
    validator = SkillValidator()
    result, manifest = validator.validate_skill_directory(skill_dir)

    if result.warnings:
        click.echo("\nWarnings:")
        for warning in result.warnings:
            click.echo(f"  - {warning}")

    if not result.is_valid:
        click.echo("\nValidation failed:")
        for error in result.errors:
            click.echo(f"  - {error}")
        return

    click.echo(f"Validation passed for {manifest.name} v{manifest.version}")

    # Package skill
    click.echo("\nPackaging skill...")
    packager = SkillPackager()
    try:
        package = packager.package_skill(skill_dir, manifest)
        click.echo(
            f"Created package: {len(package.source_files)} files, {package.package_size} bytes"
        )
        click.echo(f"Checksum: {package.checksum}")
    except (ValueError, OSError, IOError) as e:
        click.echo(f"Error packaging skill: {e}")
        return

    if dry_run:
        click.echo("\nDry run complete. Skill is ready to publish.")
        return

    # Determine registry (local or remote)
    local_registry = None
    if not registry:
        # Use local registry for testing if SKILLHUB_REGISTRY_URL not set
        if not os.getenv("SKILLHUB_REGISTRY_URL"):
            local_registry_dir = Path.home() / ".skillhub" / "registry"
            local_registry = local_registry_dir
            click.echo(f"\nUsing local registry at {local_registry}")

    # Publish to registry
    click.echo("\nPublishing to registry...")
    try:
        client = RegistryClient(
            registry_url=registry, local_registry_path=local_registry
        )

        # Check if skill already exists
        existing = client.get_skill(manifest.name, namespace)
        if existing:
            if manifest.version in existing.versions:
                click.echo(
                    f"Error: Version {manifest.version} already exists in registry"
                )
                click.echo(f"Existing versions: {', '.join(existing.versions)}")
                click.echo("Increment version in skill.json and try again")
                return
            else:
                click.echo(f"Updating existing skill (current versions: {', '.join(existing.versions)})")

        entry = client.publish_skill(package, namespace=namespace, private=private)

        click.echo("\nPublish successful!")
        click.echo(f"  Skill: {entry.skill_name}")
        if entry.namespace:
            click.echo(f"  Namespace: {entry.namespace}")
        click.echo(f"  Version: {entry.latest_version}")
        click.echo(f"  Versions: {', '.join(entry.versions)}")
        click.echo(f"  MCP Endpoint: {entry.mcp_endpoint}")

        if private:
            click.echo("\nThis is a private skill. Share the namespace for others to install.")

    except (ValueError, OSError, IOError) as e:
        click.echo(f"Error publishing skill: {e}")
        return
