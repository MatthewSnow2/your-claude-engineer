"""
Parallel Progress Display
=========================

Real-time progress tracking for parallel execution mode.
Shows worker status, tier progress, and overall completion.

Example output:
    === TIER 3: frontend + a2ui-catalog (UI components) — 6 issues ===
      Worker 0: M2A-23 TaskCard      [coding...]     2m 15s
      Worker 1: M2A-24 ProgressRing  [qa: PASS]      3m 42s
      Worker 2: M2A-25 FileTree      [code_review..] 1m 08s

      Tier: 2/6 complete | Overall: 12/38 done | Workers: 3/3 active
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


WorkerStatus = Literal[
    "starting",
    "coding",
    "code_review",
    "qa",
    "github",
    "done",
    "failed",
    "merge_conflict",
]


@dataclass
class WorkerState:
    """Tracks the current state of a parallel worker."""

    worker_index: int
    issue_id: str
    issue_title: str
    status: WorkerStatus = "starting"
    start_time: float = field(default_factory=time.monotonic)
    end_time: float | None = None

    @property
    def elapsed(self) -> float:
        end = self.end_time or time.monotonic()
        return end - self.start_time

    @property
    def elapsed_str(self) -> str:
        secs = int(self.elapsed)
        mins, secs = divmod(secs, 60)
        return f"{mins}m {secs:02d}s"

    @property
    def is_active(self) -> bool:
        return self.status not in ("done", "failed", "merge_conflict")


@dataclass
class TierProgress:
    """Tracks progress within a single execution tier."""

    tier_num: int
    description: str
    total_issues: int
    completed_ids: set[str] = field(default_factory=set)
    failed_ids: set[str] = field(default_factory=set)
    workers: dict[int, WorkerState] = field(default_factory=dict)

    @property
    def completed(self) -> int:
        return len(self.completed_ids)

    @property
    def failed(self) -> int:
        return len(self.failed_ids)

    @property
    def active_workers(self) -> int:
        return sum(1 for w in self.workers.values() if w.is_active)


@dataclass
class ParallelProgress:
    """Top-level progress tracker for parallel execution."""

    total_issues: int
    completed_issues: set[str] = field(default_factory=set)
    failed_issues: set[str] = field(default_factory=set)
    requeued_issues: set[str] = field(default_factory=set)
    current_tier: TierProgress | None = None
    start_time: float = field(default_factory=time.monotonic)
    tiers_completed: int = 0
    total_tiers: int = 0

    @property
    def overall_completed(self) -> int:
        return len(self.completed_issues)

    @property
    def elapsed_str(self) -> str:
        secs = int(time.monotonic() - self.start_time)
        mins, secs = divmod(secs, 60)
        hours, mins = divmod(mins, 60)
        if hours:
            return f"{hours}h {mins:02d}m"
        return f"{mins}m {secs:02d}s"


def print_tier_header(tier_num: int, description: str, issue_count: int) -> None:
    """Print a formatted tier header."""
    print()
    print("=" * 70)
    print(f"  TIER {tier_num}: {description} — {issue_count} issue(s)")
    print("=" * 70)
    print()


def print_worker_status(workers: dict[int, WorkerState]) -> None:
    """Print current status of all workers."""
    for idx in sorted(workers.keys()):
        w = workers[idx]
        # Truncate title to 20 chars for alignment
        title = w.issue_title[:20].ljust(20)
        status_str = f"[{w.status}]".ljust(16)
        marker = "  " if w.is_active else "  "
        print(f"  Worker {w.worker_index}: {w.issue_id} {title} {status_str} {w.elapsed_str}")


def print_progress_bar(progress: ParallelProgress) -> None:
    """Print a summary progress line."""
    tier = progress.current_tier
    tier_str = ""
    if tier:
        tier_str = f"Tier: {tier.completed}/{tier.total_issues} complete | "

    workers_active = tier.active_workers if tier else 0
    workers_total = len(tier.workers) if tier else 0

    print()
    print(
        f"  {tier_str}"
        f"Overall: {progress.overall_completed}/{progress.total_issues} done | "
        f"Workers: {workers_active}/{workers_total} active | "
        f"Elapsed: {progress.elapsed_str}"
    )

    if progress.requeued_issues:
        print(f"  Requeued (merge conflict): {', '.join(sorted(progress.requeued_issues))}")
    if progress.failed_issues:
        print(f"  Failed: {', '.join(sorted(progress.failed_issues))}")
    print()


def print_tier_summary(tier: TierProgress, merge_results: dict[str, bool]) -> None:
    """Print summary after a tier completes."""
    print()
    print(f"  --- Tier {tier.tier_num} Summary ---")
    print(f"  Completed: {tier.completed}/{tier.total_issues}")
    if tier.failed:
        print(f"  Failed: {tier.failed}")

    merged = sum(1 for v in merge_results.values() if v)
    conflicts = sum(1 for v in merge_results.values() if not v)
    print(f"  Merged: {merged} branch(es)")
    if conflicts:
        print(f"  Merge conflicts: {conflicts} (re-queued)")
    print()


def print_parallel_summary(progress: ParallelProgress) -> None:
    """Print final summary when parallel execution completes."""
    print()
    print("=" * 70)
    print("  PARALLEL EXECUTION COMPLETE")
    print("=" * 70)
    print(f"  Total issues processed: {progress.overall_completed}/{progress.total_issues}")
    print(f"  Tiers completed: {progress.tiers_completed}/{progress.total_tiers}")
    print(f"  Total elapsed time: {progress.elapsed_str}")
    if progress.failed_issues:
        print(f"  Failed issues: {', '.join(sorted(progress.failed_issues))}")
    if progress.requeued_issues:
        print(f"  Requeued issues: {', '.join(sorted(progress.requeued_issues))}")
    print("=" * 70)
    print()


def load_worker_result(result_path: Path) -> dict | None:
    """
    Load a worker result JSON file.

    Expected structure:
        {
            "issue_id": "M2A-30",
            "status": "success" | "error",
            "branch": "parallel/M2A-30",
            "files_changed": [...],
            "duration_seconds": 120.5,
            "error": ""
        }
    """
    if not result_path.exists():
        return None
    try:
        with open(result_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None
