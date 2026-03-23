"""Main CLI entry point for SkillHub."""

import click

from skillhub import __version__
from skillhub.cli.commands.init import init
from skillhub.cli.commands.publish import publish
from skillhub.cli.commands.validate import validate


@click.group()
@click.version_option(version=__version__, prog_name="skillhub")
def cli():
    """
    SkillHub CLI - Manage agent skills for MCP.

    A command-line tool for publishing, discovering, and managing
    agent skills based on the Agent Skills open standard.
    """
    pass


# Register commands
cli.add_command(init)
cli.add_command(publish)
cli.add_command(validate)


if __name__ == "__main__":
    cli()
