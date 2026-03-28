"""Reporter module for generating citation reports (stub for future features)."""

from typing import List

from llm_citation_checker.models import Statement


def generate_report(statements: List[Statement]) -> str:
    """
    Generate a report of statements and their citations.

    Args:
        statements: List of Statement objects to include in the report

    Returns:
        Formatted report string (not implemented yet)
    """
    raise NotImplementedError("Report generation not yet implemented")
