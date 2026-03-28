import re
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
    Read text from stdin and add citations to verified statements.
    """
    text = sys.stdin.read().strip()
    if not text:
        typer.echo("Error: No input provided", err=True)
        raise typer.Exit(code=1)

    facts = load_kb()

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)

    result_parts = []
    for sentence in sentences:
        match = find_match(sentence, facts)
        if match:
            result_parts.append(f"{sentence} [Source: {match.source}]")
        else:
            result_parts.append(sentence)

    typer.echo(" ".join(result_parts))


@app.command()
def report():
    """
    Generate a report of citations (not implemented yet).
    """
    typer.echo("Not implemented yet.")
