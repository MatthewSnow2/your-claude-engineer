"""Skill search command."""

import os
from pathlib import Path

import click

from skillhub.core.registry import RegistryClient


@click.command()
@click.argument("query", required=False)
@click.option("--tags", help="Filter by tags (comma-separated)")
@click.option("--limit", default=10, help="Maximum number of results (default: 10)")
@click.option(
    "--registry",
    default=None,
    help="Custom registry URL (defaults to SKILLHUB_REGISTRY_URL or local)",
)
def search(query: str, tags: str, limit: int, registry: str):
    """Search for skills in the MCP registry."""
    # Parse tags
    tag_list = None
    if tags:
        tag_list = [t.strip() for t in tags.split(",")]

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

    # Search registry
    try:
        client = RegistryClient(registry_url=registry_url, local_registry_path=local_registry)
        results = client.search_skills(query=query, tags=tag_list, limit=limit)

        if not results:
            if query:
                click.echo(f"No skills found matching '{query}'")
            else:
                click.echo("No skills found in registry")
            return

        # Display results
        click.echo(f"Found {len(results)} skill(s):\n")

        for entry in results:
            click.echo(f"  {entry.skill_name} - v{entry.latest_version}")
            click.echo(f"    Rating: {entry.rating:.1f}/5.0 | Downloads: {entry.download_count}")

            # Try to load description from registry
            if local_registry:
                skill_key = (
                    f"{entry.namespace}/{entry.skill_name}"
                    if entry.namespace
                    else entry.skill_name
                )
                manifest_path = (
                    local_registry / skill_key / entry.latest_version / "skill.json"
                )
                if manifest_path.exists():
                    import json

                    with open(manifest_path) as f:
                        manifest_data = json.load(f)
                        description = manifest_data.get("description", "")
                        if description:
                            click.echo(f"    {description}")

            click.echo(f"    Versions: {', '.join(entry.versions)}")
            click.echo("")

        click.echo(f"\nInstall with: skillhub install <skill-name>[@version]")

    except (ValueError, OSError) as e:
        click.echo(f"Error searching registry: {e}")
        return
