"""Skill validation command."""

from pathlib import Path

import click

from skillhub.core.validation import SkillValidator


@click.command()
@click.argument("manifest_path", type=click.Path(exists=True), required=False)
def validate(manifest_path: str):
    """Validate skill manifest against Agent Skills schema."""
    # Determine manifest path
    if manifest_path:
        path = Path(manifest_path)
        if path.is_dir():
            path = path / "skill.json"
    else:
        path = Path.cwd() / "skill.json"

    if not path.exists():
        click.echo(f"Error: Manifest file not found: {path}")
        return

    click.echo(f"Validating {path}...")

    # Validate
    validator = SkillValidator()
    result, manifest = validator.validate_manifest_file(path)

    # Show results
    if result.warnings:
        click.echo("\nWarnings:")
        for warning in result.warnings:
            click.echo(f"  - {warning}")

    if result.errors:
        click.echo("\nErrors:")
        for error in result.errors:
            click.echo(f"  - {error}")
        click.echo("\nValidation failed!")
        return

    if result.is_valid:
        click.echo("\nValidation passed!")
        click.echo(f"  Skill: {manifest.name} v{manifest.version}")
        click.echo(f"  Author: {manifest.author}")
        click.echo(f"  Capabilities: {len(manifest.capabilities)}")
        click.echo(f"  MCP Tools: {len(manifest.mcp_tools)}")
