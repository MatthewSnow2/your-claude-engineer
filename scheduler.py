"""
Dependency Scheduler
====================

Builds a tier-based execution plan from Linear issues in .linear_project.json.
Issues are grouped into tiers by category — issues within the same tier are
assumed independent and can run in parallel.

Tier ordering (static, deterministic):
    1. setup        — project foundation (sequential)
    2. backend      — API and data layer
    3. frontend, a2ui-catalog — UI components
    4. feature      — feature integration
    5. styling      — visual polish
    6. testing      — validation
    7. integration  — cross-cutting (sequential)
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Category-to-tier mapping. Categories not listed default to tier 4 (feature).
CATEGORY_TIERS: dict[str, int] = {
    "setup": 1,
    "backend": 2,
    "frontend": 3,
    "a2ui-catalog": 3,
    "feature": 4,
    "styling": 5,
    "testing": 6,
    "integration": 7,
}

# Tiers that should run sequentially (one issue at a time)
SEQUENTIAL_TIERS: set[int] = {1, 7}

# Human-readable tier descriptions
TIER_DESCRIPTIONS: dict[int, str] = {
    1: "setup (project foundation)",
    2: "backend (API and data layer)",
    3: "frontend + a2ui-catalog (UI components)",
    4: "feature (integration features)",
    5: "styling (visual polish)",
    6: "testing (validation)",
    7: "integration (cross-cutting)",
}

DEFAULT_TIER: int = 4


@dataclass
class ExecutionTier:
    """A group of issues that can execute in parallel."""

    tier: int
    issue_ids: list[str]
    description: str
    sequential: bool = False

    @property
    def size(self) -> int:
        return len(self.issue_ids)


@dataclass
class ParallelPlan:
    """Complete execution plan with tiered issue groups."""

    tiers: list[ExecutionTier]
    max_parallelism: int
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_issues: int = 0

    def __post_init__(self) -> None:
        self.total_issues = sum(t.size for t in self.tiers)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "created_at": self.created_at,
            "max_parallelism": self.max_parallelism,
            "total_issues": self.total_issues,
            "tiers": [
                {
                    "tier": t.tier,
                    "description": t.description,
                    "sequential": t.sequential,
                    "issue_ids": t.issue_ids,
                }
                for t in self.tiers
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ParallelPlan":
        """Deserialize from JSON-compatible dict."""
        tiers = [
            ExecutionTier(
                tier=t["tier"],
                issue_ids=t["issue_ids"],
                description=t["description"],
                sequential=t.get("sequential", False),
            )
            for t in data["tiers"]
        ]
        return cls(
            tiers=tiers,
            max_parallelism=data["max_parallelism"],
            created_at=data.get("created_at", ""),
        )


def build_plan(
    issues: list[dict[str, str]],
    max_parallelism: int = 2,
) -> ParallelPlan:
    """
    Build a tier-based execution plan from a list of issues.

    Args:
        issues: List of issue dicts with at least 'id' and 'category' keys.
        max_parallelism: Maximum concurrent workers.

    Returns:
        ParallelPlan with issues grouped into execution tiers.
    """
    # Group issues by tier number
    tier_groups: dict[int, list[str]] = {}
    for issue in issues:
        category = issue.get("category", "").lower()
        tier_num = CATEGORY_TIERS.get(category, DEFAULT_TIER)
        tier_groups.setdefault(tier_num, []).append(issue["id"])

    # Build ordered tiers
    tiers: list[ExecutionTier] = []
    for tier_num in sorted(tier_groups.keys()):
        issue_ids = tier_groups[tier_num]
        tiers.append(
            ExecutionTier(
                tier=tier_num,
                issue_ids=issue_ids,
                description=TIER_DESCRIPTIONS.get(tier_num, f"tier {tier_num}"),
                sequential=tier_num in SEQUENTIAL_TIERS,
            )
        )

    return ParallelPlan(tiers=tiers, max_parallelism=max_parallelism)


def get_ready_issues(
    plan: ParallelPlan,
    completed: set[str],
) -> tuple[list[str], ExecutionTier | None]:
    """
    Get the next batch of issues ready to execute.

    Returns issues from the first tier that has incomplete issues.
    All prior tiers must be fully complete before advancing.

    Args:
        plan: The execution plan.
        completed: Set of issue IDs already completed.

    Returns:
        Tuple of (ready_issue_ids, current_tier). Empty list and None if all done.
    """
    for tier in plan.tiers:
        remaining = [iid for iid in tier.issue_ids if iid not in completed]
        if not remaining:
            continue  # This tier is done, check next

        # This tier has work — return its remaining issues
        return remaining, tier

    # All tiers complete
    return [], None


def save_plan(plan: ParallelPlan, project_dir: Path) -> Path:
    """Save plan to .parallel_plan.json in the project directory."""
    plan_path = project_dir / ".parallel_plan.json"
    with open(plan_path, "w") as f:
        json.dump(plan.to_dict(), f, indent=2)
    return plan_path


def load_plan(project_dir: Path) -> ParallelPlan | None:
    """Load plan from .parallel_plan.json, or None if not found."""
    plan_path = project_dir / ".parallel_plan.json"
    if not plan_path.exists():
        return None
    with open(plan_path, "r") as f:
        data = json.load(f)
    return ParallelPlan.from_dict(data)
