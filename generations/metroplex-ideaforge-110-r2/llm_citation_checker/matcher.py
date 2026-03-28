from typing import List, Optional

from llm_citation_checker.models import Fact


def find_match(sentence: str, facts: List[Fact]) -> Optional[Fact]:
    """
    Find the first matching fact for the given sentence.

    Performs case-insensitive substring search to check if any fact
    is contained within the sentence.

    Args:
        sentence: The sentence to search for matches
        facts: List of facts to search against

    Returns:
        The first matching Fact, or None if no match found
    """
    sentence_lower = sentence.lower()

    for fact in facts:
        if fact.fact.lower() in sentence_lower:
            return fact

    return None
