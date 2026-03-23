"""Skill list command."""

import click

from skillhub.core.cache import SkillCacheManager


@click.command(name="list")
@click.option("--installed", is_flag=True, help="Show only locally cached skills")
def list_skills(installed: bool):
    """List available or installed skills."""
    if not installed:
        click.echo("Error: Only --installed flag is currently supported")
        click.echo("Use 'skillhub list --installed' to show cached skills")
        click.echo("Use 'skillhub search' to discover available skills")
        return

    # List installed skills from cache
    cache_manager = SkillCacheManager()
    skills = cache_manager.list_installed()

    if not skills:
        click.echo("No skills installed in local cache")
        click.echo(f"Cache location: {cache_manager.get_cache_dir()}")
        click.echo("\nInstall skills with: skillhub install <skill-name>")
        return

    click.echo(f"Installed skills ({len(skills)}):\n")
    click.echo(f"Cache location: {cache_manager.get_cache_dir()}\n")

    for skill in skills:
        click.echo(f"  {skill.name} - v{skill.version}")
        if skill.manifest.description:
            click.echo(f"    {skill.manifest.description}")
        click.echo(f"    Location: {skill.install_path}")
        click.echo(f"    License: {skill.manifest.license}")

        if skill.manifest.dependencies:
            deps = ", ".join(skill.manifest.dependencies.keys())
            click.echo(f"    Dependencies: {deps}")

        click.echo("")

    click.echo(f"Total: {len(skills)} skill(s)")
