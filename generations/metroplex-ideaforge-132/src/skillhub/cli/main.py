"""Main CLI entry point for SkillHub."""

import click

from skillhub import __version__
from skillhub.cli.commands.init import init
from skillhub.cli.commands.install import install
from skillhub.cli.commands.list_cmd import list_skills
from skillhub.cli.commands.logs import logs
from skillhub.cli.commands.publish import publish
from skillhub.cli.commands.search import search
from skillhub.cli.commands.serve import serve
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
cli.add_command(search)
cli.add_command(install)
cli.add_command(list_skills)
cli.add_command(serve)
cli.add_command(logs)


if __name__ == "__main__":
    cli()
