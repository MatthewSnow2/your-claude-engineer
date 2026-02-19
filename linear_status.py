"""
Linear Issue Status Checker
============================

Queries Linear via the Arcade SDK to determine which issues are already
Done, allowing the parallel coordinator to skip completed work and resume
from where it left off.

Uses the synchronous Arcade client (not MCP) so it can run outside of a
Claude SDK session.
"""

import os
from typing import Any

from arcadepy import Arcade

from arcade_config import ARCADE_API_KEY, ARCADE_USER_ID


# Linear workflow state types that count as "completed"
COMPLETED_STATE_TYPES: set[str] = {"completed"}

# State types that count as "cancelled" (skip these too)
CANCELLED_STATE_TYPES: set[str] = {"canceled"}


def _create_arcade_client() -> Arcade:
    """Create an Arcade SDK client for direct API calls."""
    if not ARCADE_API_KEY:
        raise ValueError(
            "ARCADE_API_KEY not set. Cannot check Linear issue statuses.\n"
            "Set it in ~/.env.shared or environment."
        )
    return Arcade(api_key=ARCADE_API_KEY)


def get_issue_status(client: Arcade, issue_identifier: str) -> dict[str, Any]:
    """
    Get the current status of a single Linear issue.

    Args:
        client: Arcade SDK client.
        issue_identifier: Linear issue identifier (e.g., "M2A-30").

    Returns:
        Dict with keys: identifier, title, state_name, state_type, completed_at.
        Returns state_type="unknown" if the issue can't be found.
    """
    try:
        result = client.tools.execute(
            tool_name="Linear_GetIssue",
            input={"issue_id": issue_identifier},
            user_id=ARCADE_USER_ID,
        )
        issue = result.output.value.get("issue", {})
        state = issue.get("state", {})

        return {
            "identifier": issue.get("identifier", issue_identifier),
            "title": issue.get("title", ""),
            "state_name": state.get("name", "Unknown"),
            "state_type": state.get("type", "unknown"),
            "completed_at": issue.get("completed_at"),
        }
    except Exception as e:
        print(f"  [linear] Warning: Could not fetch status for {issue_identifier}: {e}")
        return {
            "identifier": issue_identifier,
            "title": "",
            "state_name": "Unknown",
            "state_type": "unknown",
            "completed_at": None,
        }


def check_issue_statuses(
    issue_identifiers: list[str],
) -> tuple[set[str], set[str], dict[str, dict[str, Any]]]:
    """
    Check the current Linear status of multiple issues.

    Makes one API call per issue via the Arcade SDK. Typically takes
    ~0.2s per call (~8s for 38 issues).

    Args:
        issue_identifiers: List of Linear issue identifiers (e.g., ["M2A-11", "M2A-12"]).

    Returns:
        Tuple of:
        - completed: Set of issue identifiers that are Done.
        - cancelled: Set of issue identifiers that are Cancelled/Duplicate.
        - status_map: Full status dict for each issue.
    """
    client = _create_arcade_client()

    completed: set[str] = set()
    cancelled: set[str] = set()
    status_map: dict[str, dict[str, Any]] = {}

    print(f"  [linear] Checking status of {len(issue_identifiers)} issues...")

    for i, identifier in enumerate(issue_identifiers):
        status = get_issue_status(client, identifier)
        status_map[identifier] = status

        if status["state_type"] in COMPLETED_STATE_TYPES:
            completed.add(identifier)
        elif status["state_type"] in CANCELLED_STATE_TYPES:
            cancelled.add(identifier)

        # Progress indicator every 10 issues
        if (i + 1) % 10 == 0:
            print(f"  [linear] ... checked {i + 1}/{len(issue_identifiers)}")

    print(
        f"  [linear] Status check complete: "
        f"{len(completed)} done, {len(cancelled)} cancelled, "
        f"{len(issue_identifiers) - len(completed) - len(cancelled)} remaining"
    )

    return completed, cancelled, status_map


def print_status_summary(
    status_map: dict[str, dict[str, Any]],
    completed: set[str],
    cancelled: set[str],
) -> None:
    """Print a formatted summary of issue statuses."""
    print()
    print("  Linear Issue Status:")

    # Group by state
    by_state: dict[str, list[str]] = {}
    for identifier, status in status_map.items():
        state_name = status["state_name"]
        by_state.setdefault(state_name, []).append(identifier)

    for state_name in sorted(by_state.keys()):
        ids = sorted(by_state[state_name])
        print(f"    {state_name}: {len(ids)} — {', '.join(ids[:5])}", end="")
        if len(ids) > 5:
            print(f" (+{len(ids) - 5} more)", end="")
        print()

    remaining = len(status_map) - len(completed) - len(cancelled)
    print(f"\n  Will process: {remaining} issue(s) (skipping {len(completed)} done, {len(cancelled)} cancelled)")
    print()
