import sys
import typer

from llm_citation_checker.kb import load_kb
from llm_citation_checker.matcher import find_match

app = typer.Typer()


@app.command()
def lookup():
    """
    Read text from stdin and lookup matching facts in the knowledge base.
    """
    # Read from stdin
    text = sys.stdin.read().strip()

    # Load knowledge base
    facts = load_kb()

    # Find match
    match = find_match(text, facts)

    if match:
        typer.echo(f"Matched fact: {match.fact}")
        typer.echo(f"Source: {match.source}")
    else:
        typer.echo("No matching fact found.")


@app.command()
def cite():
    """
    Scan text and add citation markers (not implemented yet).
    """
    typer.echo("Not implemented yet.")


@app.command()
def report():
    """
    Generate a report of citations (not implemented yet).
    """
    typer.echo("Not implemented yet.")
