"""Command-line interface for CommitNarrative."""

import sys
import click
from commitnarrative.extractor import extract_commits


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """CommitNarrative - Transform Git commits into social media updates."""
    pass


@cli.command()
@click.option(
    "--repo",
    default=".",
    help="Path to Git repository (default: current directory)",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
)
@click.option(
    "--count",
    default=5,
    help="Number of commits to extract (default: 5)",
    type=click.IntRange(min=1),
)
def extract(repo, count):
    """Extract commit messages from a Git repository.

    Retrieves the last N commit messages, strips conventional commit
    prefixes (feat:, fix:, etc.), and outputs them one per line.
    """
    try:
        messages = extract_commits(repo_path=repo, count=count)

        for message in messages:
            click.echo(message)

    except (FileNotFoundError, NotADirectoryError, ValueError, RuntimeError) as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    cli()
