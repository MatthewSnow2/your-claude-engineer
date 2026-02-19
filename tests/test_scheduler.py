"""Tests for scheduler.py — tier-based dependency planning."""

import json
import tempfile
from pathlib import Path

import pytest

from scheduler import (
    CATEGORY_TIERS,
    DEFAULT_TIER,
    SEQUENTIAL_TIERS,
    ExecutionTier,
    ParallelPlan,
    build_plan,
    get_ready_issues,
    load_plan,
    save_plan,
)


# --- Fixtures ---


@pytest.fixture
def sample_issues() -> list[dict[str, str]]:
    """Minimal issue set covering all categories."""
    return [
        {"id": "T-1", "title": "Init project", "category": "setup", "priority": "High"},
        {"id": "T-2", "title": "Install deps", "category": "setup", "priority": "High"},
        {"id": "T-3", "title": "API endpoint", "category": "backend", "priority": "High"},
        {"id": "T-4", "title": "DB schema", "category": "backend", "priority": "Medium"},
        {"id": "T-5", "title": "Dashboard page", "category": "frontend", "priority": "High"},
        {"id": "T-6", "title": "TaskCard", "category": "a2ui-catalog", "priority": "High"},
        {"id": "T-7", "title": "ProgressRing", "category": "a2ui-catalog", "priority": "Medium"},
        {"id": "T-8", "title": "User auth", "category": "feature", "priority": "High"},
        {"id": "T-9", "title": "Dark mode", "category": "styling", "priority": "Low"},
        {"id": "T-10", "title": "E2E tests", "category": "testing", "priority": "High"},
        {"id": "T-11", "title": "CI pipeline", "category": "integration", "priority": "High"},
    ]


@pytest.fixture
def gen_ui_issues() -> list[dict[str, str]]:
    """Load real gen-ui-dashboard issues if available."""
    path = Path("/home/ubuntu/projects/ai-generations/gen-ui-dashboard/.linear_project.json")
    if not path.exists():
        pytest.skip("gen-ui-dashboard data not available")
    with open(path) as f:
        return json.load(f)["issues"]


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    return tmp_path


# --- build_plan tests ---


class TestBuildPlan:
    def test_groups_by_category(self, sample_issues: list[dict[str, str]]) -> None:
        plan = build_plan(sample_issues, max_parallelism=2)
        assert plan.total_issues == 11
        assert len(plan.tiers) == 7  # All 7 tiers represented

    def test_tier_ordering_ascending(self, sample_issues: list[dict[str, str]]) -> None:
        plan = build_plan(sample_issues, max_parallelism=2)
        tier_nums = [t.tier for t in plan.tiers]
        assert tier_nums == sorted(tier_nums)

    def test_setup_is_sequential(self, sample_issues: list[dict[str, str]]) -> None:
        plan = build_plan(sample_issues, max_parallelism=3)
        setup_tier = next(t for t in plan.tiers if t.tier == 1)
        assert setup_tier.sequential is True

    def test_integration_is_sequential(self, sample_issues: list[dict[str, str]]) -> None:
        plan = build_plan(sample_issues, max_parallelism=3)
        integration_tier = next(t for t in plan.tiers if t.tier == 7)
        assert integration_tier.sequential is True

    def test_backend_is_parallel(self, sample_issues: list[dict[str, str]]) -> None:
        plan = build_plan(sample_issues, max_parallelism=3)
        backend_tier = next(t for t in plan.tiers if t.tier == 2)
        assert backend_tier.sequential is False

    def test_frontend_and_a2ui_same_tier(self, sample_issues: list[dict[str, str]]) -> None:
        plan = build_plan(sample_issues, max_parallelism=2)
        tier3 = next(t for t in plan.tiers if t.tier == 3)
        assert "T-5" in tier3.issue_ids  # frontend
        assert "T-6" in tier3.issue_ids  # a2ui-catalog
        assert "T-7" in tier3.issue_ids  # a2ui-catalog

    def test_max_parallelism_stored(self) -> None:
        plan = build_plan([{"id": "X-1", "category": "backend"}], max_parallelism=5)
        assert plan.max_parallelism == 5

    def test_unknown_category_defaults_to_feature_tier(self) -> None:
        issues = [{"id": "X-1", "category": "unknown_category"}]
        plan = build_plan(issues, max_parallelism=2)
        assert plan.tiers[0].tier == DEFAULT_TIER

    def test_empty_issues(self) -> None:
        plan = build_plan([], max_parallelism=2)
        assert plan.total_issues == 0
        assert plan.tiers == []

    def test_single_issue(self) -> None:
        issues = [{"id": "X-1", "category": "setup"}]
        plan = build_plan(issues, max_parallelism=2)
        assert plan.total_issues == 1
        assert len(plan.tiers) == 1

    def test_gen_ui_dashboard_38_issues(self, gen_ui_issues: list[dict[str, str]]) -> None:
        plan = build_plan(gen_ui_issues, max_parallelism=3)
        assert plan.total_issues == 38
        assert len(plan.tiers) == 7


# --- get_ready_issues tests ---


class TestGetReadyIssues:
    def test_first_tier_returned_initially(self, sample_issues: list[dict[str, str]]) -> None:
        plan = build_plan(sample_issues, max_parallelism=2)
        ready, tier = get_ready_issues(plan, set())
        assert tier is not None
        assert tier.tier == 1
        assert set(ready) == {"T-1", "T-2"}

    def test_advances_after_tier_complete(self, sample_issues: list[dict[str, str]]) -> None:
        plan = build_plan(sample_issues, max_parallelism=2)
        completed = {"T-1", "T-2"}  # All setup done
        ready, tier = get_ready_issues(plan, completed)
        assert tier is not None
        assert tier.tier == 2
        assert "T-3" in ready and "T-4" in ready

    def test_blocks_until_tier_fully_complete(self, sample_issues: list[dict[str, str]]) -> None:
        plan = build_plan(sample_issues, max_parallelism=2)
        completed = {"T-1"}  # Only 1 of 2 setup issues done
        ready, tier = get_ready_issues(plan, completed)
        assert tier is not None
        assert tier.tier == 1  # Still tier 1
        assert ready == ["T-2"]  # Only remaining issue

    def test_all_done_returns_empty(self, sample_issues: list[dict[str, str]]) -> None:
        plan = build_plan(sample_issues, max_parallelism=2)
        all_ids = {issue["id"] for issue in sample_issues}
        ready, tier = get_ready_issues(plan, all_ids)
        assert ready == []
        assert tier is None


# --- ExecutionTier tests ---


class TestExecutionTier:
    def test_size_property(self) -> None:
        tier = ExecutionTier(tier=1, issue_ids=["A", "B", "C"], description="test")
        assert tier.size == 3

    def test_empty_tier(self) -> None:
        tier = ExecutionTier(tier=1, issue_ids=[], description="test")
        assert tier.size == 0


# --- Serialization tests ---


class TestSerialization:
    def test_plan_to_dict(self, sample_issues: list[dict[str, str]]) -> None:
        plan = build_plan(sample_issues, max_parallelism=3)
        d = plan.to_dict()
        assert d["total_issues"] == 11
        assert d["max_parallelism"] == 3
        assert len(d["tiers"]) == 7
        assert all("tier" in t and "issue_ids" in t for t in d["tiers"])

    def test_plan_from_dict(self, sample_issues: list[dict[str, str]]) -> None:
        plan = build_plan(sample_issues, max_parallelism=3)
        d = plan.to_dict()
        restored = ParallelPlan.from_dict(d)
        assert restored.total_issues == plan.total_issues
        assert restored.max_parallelism == plan.max_parallelism
        assert len(restored.tiers) == len(plan.tiers)

    def test_round_trip_json(self, sample_issues: list[dict[str, str]], tmp_project: Path) -> None:
        plan = build_plan(sample_issues, max_parallelism=2)
        save_plan(plan, tmp_project)
        loaded = load_plan(tmp_project)
        assert loaded is not None
        assert loaded.total_issues == plan.total_issues
        for orig, loaded_t in zip(plan.tiers, loaded.tiers):
            assert orig.tier == loaded_t.tier
            assert orig.issue_ids == loaded_t.issue_ids
            assert orig.sequential == loaded_t.sequential

    def test_load_plan_missing_file(self, tmp_project: Path) -> None:
        result = load_plan(tmp_project)
        assert result is None

    def test_save_creates_file(self, sample_issues: list[dict[str, str]], tmp_project: Path) -> None:
        plan = build_plan(sample_issues, max_parallelism=2)
        path = save_plan(plan, tmp_project)
        assert path.exists()
        assert path.name == ".parallel_plan.json"


# --- Category tier mapping tests ---


class TestCategoryMapping:
    def test_all_expected_categories_mapped(self) -> None:
        expected = {"setup", "backend", "frontend", "a2ui-catalog", "feature", "styling", "testing", "integration"}
        assert expected == set(CATEGORY_TIERS.keys())

    def test_sequential_tiers_are_first_and_last(self) -> None:
        assert 1 in SEQUENTIAL_TIERS
        assert 7 in SEQUENTIAL_TIERS
        assert len(SEQUENTIAL_TIERS) == 2
