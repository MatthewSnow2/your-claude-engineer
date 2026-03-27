"""CLI entry point for csuite."""
import click
import os
from pathlib import Path

from .parser import CodebaseParser
from .diagram import generate_mermaid_diagram
from .docs import generate_markdown_docs


@click.group()
def cli():
    """csuite - Codebase visualization and documentation tool."""
    pass


@cli.command()
@click.option('--path', required=True, type=click.Path(exists=True),
              help='Path to the Python codebase directory')
def parse(path: str):
    """Parse a Python codebase and display summary statistics."""
    parser = CodebaseParser(path)
    modules = parser.parse()
    summary = parser.get_summary()

    click.echo(
        f"Found {summary['modules']} modules, "
        f"{summary['classes']} classes, "
        f"{summary['functions']} functions, "
        f"{summary['imports']} imports"
    )


@cli.command()
@click.option('--path', required=True, type=click.Path(exists=True),
              help='Path to the Python codebase directory')
@click.option('--output', required=True, type=click.Path(),
              help='Output file path for the Mermaid diagram')
def diagram(path: str, output: str):
    """Generate a Mermaid class diagram from the codebase."""
    parser = CodebaseParser(path)
    modules = parser.parse()

    try:
        mermaid_content = generate_mermaid_diagram(modules)
        # Respect CSUITE_OUTPUT_DIR environment variable
        output_dir = os.getenv('CSUITE_OUTPUT_DIR', '.')
        output_path = Path(output_dir) / output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(mermaid_content)
        click.echo(f"Mermaid diagram written to {output_path}")
    except NotImplementedError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option('--path', required=True, type=click.Path(exists=True),
              help='Path to the Python codebase directory')
@click.option('--output', required=True, type=click.Path(),
              help='Output file path for the Markdown documentation')
def docs(path: str, output: str):
    """Generate Markdown documentation from the codebase."""
    parser = CodebaseParser(path)
    modules = parser.parse()

    try:
        markdown_content = generate_markdown_docs(modules)
        # Respect CSUITE_OUTPUT_DIR environment variable
        output_dir = os.getenv('CSUITE_OUTPUT_DIR', '.')
        output_path = Path(output_dir) / output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown_content)
        click.echo(f"Markdown documentation written to {output_path}")
    except NotImplementedError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


if __name__ == '__main__':
    cli()
