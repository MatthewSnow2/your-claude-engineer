"""
Parallel Coordinator
====================

Main parallel execution loop. Coordinates multiple worker subprocesses
to implement independent Linear issues concurrently using git worktrees.

Architecture:
    - Each worker is a separate OS process (avoids anyio SDK conflicts)
    - Each worker gets its own git worktree (filesystem isolation)
    - Workers within the same tier run in parallel (asyncio.gather)
    - Tiers execute sequentially (later tiers depend on earlier ones)
    - Merge conflicts trigger re-queuing for sequential execution

Usage:
    Called from autonomous_agent_demo.py when --parallel flag is set.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from scheduler import (
    ParallelPlan,
    build_plan,
    get_ready_issues,
    load_plan,
    save_plan,
)
from merge import (
    MergeResult,
    cleanup_worktrees,
    create_worktree,
    delete_branch,
    ensure_git_initialized,
    get_results_dir,
    get_worktree_dir,
    merge_branch,
    remove_worktree,
)
from parallel_progress import (
    ParallelProgress,
    TierProgress,
    WorkerState,
    load_worker_result,
    print_parallel_summary,
    print_progress_bar,
    print_tier_header,
    print_tier_summary,
    print_worker_status,
)
from progress import (
    LinearProjectState,
    load_linear_project_state,
    is_linear_initialized,
    print_progress_summary,
)
from linear_status import check_issue_statuses, print_status_summary
from agent import run_autonomous_agent


# Branch name prefix for parallel workers
BRANCH_PREFIX: str = "parallel"


def _make_branch_name(issue_id: str) -> str:
    """Create a branch name for a parallel worker issue."""
    return f"{BRANCH_PREFIX}/{issue_id}"


def _build_worker_command(
    issue: dict,
    worktree_dir: Path,
    branch: str,
    project_dir: Path,
    model: str,
    result_path: Path,
) -> list[str]:
    """
    Build the command list for spawning a worker subprocess.

    Uses `python -m worker` so the worker runs as a module with its own
    event loop and SDK client instance.
    """
    return [
        sys.executable, "-m", "worker",
        "--issue-id", issue["id"],
        "--issue-title", issue.get("title", ""),
        "--issue-category", issue.get("category", ""),
        "--issue-priority", issue.get("priority", "Medium"),
        "--worktree-dir", str(worktree_dir),
        "--branch", branch,
        "--project-dir", str(project_dir),
        "--model", model,
        "--result-path", str(result_path),
    ]


async def _spawn_worker(
    cmd: list[str],
    issue_id: str,
    worker_index: int,
) -> tuple[str, int]:
    """
    Spawn a worker subprocess and wait for it to complete.

    Args:
        cmd: Full command list for the subprocess.
        issue_id: Issue ID for logging.
        worker_index: Worker index for display.

    Returns:
        Tuple of (issue_id, returncode).
    """
    print(f"  [coordinator] Spawning worker {worker_index} for {issue_id}")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(Path(__file__).parent),  # Run from project harness dir
    )

    # Stream output line by line
    assert proc.stdout is not None
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        print(line.decode().rstrip(), flush=True)

    await proc.wait()
    returncode = proc.returncode or 0

    if returncode == 0:
        print(f"  [coordinator] Worker {worker_index} ({issue_id}) completed successfully")
    else:
        print(f"  [coordinator] Worker {worker_index} ({issue_id}) failed (exit code {returncode})")

    return issue_id, returncode


async def _run_tier_parallel(
    tier_issues: list[dict],
    project_dir: Path,
    model: str,
    max_workers: int,
    progress: ParallelProgress,
) -> dict[str, dict]:
    """
    Run a batch of issues in parallel within a single tier.

    Issues are batched by max_workers. If there are more issues than
    workers, they run in waves.

    Args:
        tier_issues: List of issue dicts for this batch.
        project_dir: Main project directory.
        model: Full Claude model ID.
        max_workers: Maximum concurrent workers.
        progress: Progress tracker.

    Returns:
        Dict mapping issue_id to result dict.
    """
    results_dir = get_results_dir(project_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    all_results: dict[str, dict] = {}

    # Process in waves of max_workers
    for wave_start in range(0, len(tier_issues), max_workers):
        wave = tier_issues[wave_start:wave_start + max_workers]

        print(f"\n  [coordinator] Starting wave: {len(wave)} worker(s)")

        # Set up worktrees and commands
        spawn_tasks = []
        for i, issue in enumerate(wave):
            worker_index = wave_start + i
            issue_id = issue["id"]
            branch = _make_branch_name(issue_id)
            worktree_dir = get_worktree_dir(project_dir, worker_index)
            result_path = results_dir / f"{issue_id}.json"

            # Create worktree
            success = await create_worktree(project_dir, worktree_dir, branch)
            if not success:
                all_results[issue_id] = {
                    "issue_id": issue_id,
                    "status": "error",
                    "branch": branch,
                    "files_changed": [],
                    "duration_seconds": 0,
                    "error": "Failed to create worktree",
                }
                continue

            # Update progress
            if progress.current_tier:
                progress.current_tier.workers[worker_index] = WorkerState(
                    worker_index=worker_index,
                    issue_id=issue_id,
                    issue_title=issue.get("title", ""),
                    status="starting",
                )

            # Build spawn command
            cmd = _build_worker_command(
                issue, worktree_dir, branch, project_dir, model, result_path,
            )
            spawn_tasks.append(_spawn_worker(cmd, issue_id, worker_index))

        if not spawn_tasks:
            continue

        # Run workers in parallel
        worker_results = await asyncio.gather(*spawn_tasks, return_exceptions=True)

        # Collect results and clean up worktrees
        for i, (issue, wr) in enumerate(zip(wave, worker_results)):
            worker_index = wave_start + i
            issue_id = issue["id"]
            result_path = results_dir / f"{issue_id}.json"
            worktree_dir = get_worktree_dir(project_dir, worker_index)

            if isinstance(wr, Exception):
                print(f"  [coordinator] Worker {issue_id} raised exception: {wr}")
                all_results[issue_id] = {
                    "issue_id": issue_id,
                    "status": "error",
                    "branch": _make_branch_name(issue_id),
                    "files_changed": [],
                    "duration_seconds": 0,
                    "error": str(wr),
                }
            else:
                # Load result from file
                result = load_worker_result(result_path)
                if result:
                    all_results[issue_id] = result
                else:
                    all_results[issue_id] = {
                        "issue_id": issue_id,
                        "status": "error",
                        "branch": _make_branch_name(issue_id),
                        "files_changed": [],
                        "duration_seconds": 0,
                        "error": "No result file produced",
                    }

            # Clean up worktree (branch preserved for merging)
            await remove_worktree(project_dir, worktree_dir)

            # Update progress
            if progress.current_tier:
                ws = progress.current_tier.workers.get(worker_index)
                if ws:
                    result_data = all_results.get(issue_id, {})
                    ws.status = "done" if result_data.get("status") == "success" else "failed"
                    ws.end_time = time.monotonic()

        # Show progress after each wave
        print_worker_status(progress.current_tier.workers if progress.current_tier else {})
        print_progress_bar(progress)

    return all_results


async def _run_tier_sequential(
    tier_issues: list[dict],
    project_dir: Path,
    model: str,
    progress: ParallelProgress,
) -> dict[str, dict]:
    """
    Run issues sequentially (for setup/integration tiers or single issues).

    Still uses worktrees for isolation consistency, but one at a time.
    """
    return await _run_tier_parallel(
        tier_issues, project_dir, model,
        max_workers=1, progress=progress,
    )


async def run_parallel_agent(
    project_dir: Path,
    model: str,
    max_workers: int = 2,
    max_iterations: int | None = None,
) -> None:
    """
    Run the parallel execution coordinator.

    This is the main entry point for --parallel mode. It:
    1. Ensures the project is initialized (runs sequential init if needed)
    2. Builds or loads the parallel execution plan
    3. Executes tiers in order, parallelizing within each tier
    4. Merges worker branches and handles conflicts

    Args:
        project_dir: Directory for the project.
        model: Full Claude model ID.
        max_workers: Maximum concurrent worker processes (1-3).
        max_iterations: Not used in parallel mode (reserved for future).

    Raises:
        ValueError: If max_workers is not 1-3 or project is not initialized.
    """
    if max_workers < 1 or max_workers > 5:
        raise ValueError(f"max_workers must be 1-5, got {max_workers}")

    print("\n" + "=" * 70)
    print("  PARALLEL EXECUTION MODE")
    print("=" * 70)
    print(f"\nProject directory: {project_dir}")
    print(f"Model: {model}")
    print(f"Max workers: {max_workers}")
    print()

    # Create project directory
    project_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1: Ensure project is initialized
    if not is_linear_initialized(project_dir):
        print("Project not initialized — running sequential initialization first...")
        print("(Parallel mode requires existing Linear issues to schedule)")
        print()
        # Run one iteration of sequential init
        await run_autonomous_agent(
            project_dir=project_dir,
            model=model,
            max_iterations=1,
        )

        if not is_linear_initialized(project_dir):
            print("\nError: Project initialization did not complete.")
            print("Run without --parallel first to initialize the project.")
            return

    # Load project state
    state = load_linear_project_state(project_dir)
    if not state:
        print("Error: Could not load .linear_project.json")
        return

    issues: list[dict] = state.get("issues", [])  # type: ignore[assignment]
    if not issues:
        print("Error: No issues found in .linear_project.json")
        return

    # Verify git is initialized
    if not await ensure_git_initialized(project_dir):
        print("Error: Project directory is not a git repository.")
        print("Run without --parallel first to set up the project.")
        return

    # Phase 2: Build or load execution plan
    plan = load_plan(project_dir)
    if plan is None:
        print("Building parallel execution plan...")
        plan = build_plan(issues, max_parallelism=max_workers)
        save_plan(plan, project_dir)
        print(f"  Plan saved to .parallel_plan.json")
    else:
        print(f"  Loaded existing plan from .parallel_plan.json")

    # Display plan
    print(f"\n  Execution Plan: {plan.total_issues} issues in {len(plan.tiers)} tiers")
    for tier in plan.tiers:
        mode = "sequential" if tier.sequential else f"parallel (up to {max_workers})"
        print(f"    Tier {tier.tier}: {tier.description} — {tier.size} issue(s) [{mode}]")
    print()

    # Build issue lookup
    issue_lookup: dict[str, dict] = {issue["id"]: issue for issue in issues}

    # Phase 2b: Check Linear for current issue statuses
    # This makes --parallel resumable: already-Done issues are skipped
    all_identifiers = [issue["id"] for issue in issues]
    completed, cancelled, status_map = check_issue_statuses(all_identifiers)
    print_status_summary(status_map, completed, cancelled)

    # Also skip cancelled issues (treat as completed for scheduling purposes)
    completed = completed | cancelled

    # Initialize progress tracking
    remaining_count = plan.total_issues - len(completed)
    progress = ParallelProgress(
        total_issues=plan.total_issues,
        completed_issues=set(completed),
        total_tiers=len(plan.tiers),
    )

    requeued: list[dict] = []  # Issues to retry sequentially after merge conflicts

    if remaining_count == 0:
        print("All issues are already Done in Linear!")
        print("Run without --parallel to finalize project completion.")
        return

    # Phase 3: Execute tiers
    for tier in plan.tiers:
        ready_ids, current_tier = get_ready_issues(plan, completed)
        if not ready_ids or current_tier is None:
            break

        # Only process issues from the current tier
        tier_issue_ids = [iid for iid in current_tier.issue_ids if iid not in completed]
        tier_issues = [issue_lookup[iid] for iid in tier_issue_ids if iid in issue_lookup]

        if not tier_issues:
            progress.tiers_completed += 1
            continue

        # Set up tier progress
        tier_progress = TierProgress(
            tier_num=current_tier.tier,
            description=current_tier.description,
            total_issues=len(tier_issues),
        )
        progress.current_tier = tier_progress

        print_tier_header(current_tier.tier, current_tier.description, len(tier_issues))

        # Choose execution strategy
        if current_tier.sequential or len(tier_issues) == 1:
            results = await _run_tier_sequential(
                tier_issues, project_dir, model, progress,
            )
        else:
            results = await _run_tier_parallel(
                tier_issues, project_dir, model, max_workers, progress,
            )

        # Phase 4: Merge successful branches
        merge_results: dict[str, bool] = {}
        for issue_id, result in results.items():
            if result.get("status") == "success":
                branch = result.get("branch", _make_branch_name(issue_id))
                mr = await merge_branch(project_dir, branch)

                if mr.success:
                    merge_results[issue_id] = True
                    completed.add(issue_id)
                    progress.completed_issues.add(issue_id)
                    tier_progress.completed_ids.add(issue_id)
                    await delete_branch(project_dir, branch)
                elif mr.conflict:
                    merge_results[issue_id] = False
                    progress.requeued_issues.add(issue_id)
                    requeued.append(issue_lookup[issue_id])
                    print(f"  [coordinator] {issue_id} re-queued due to merge conflict")
                else:
                    merge_results[issue_id] = False
                    progress.failed_issues.add(issue_id)
                    tier_progress.failed_ids.add(issue_id)
            else:
                # Worker failed
                progress.failed_issues.add(issue_id)
                tier_progress.failed_ids.add(issue_id)

        print_tier_summary(tier_progress, merge_results)
        progress.tiers_completed += 1

    # Phase 5: Handle re-queued issues (sequential retry)
    if requeued:
        print("\n" + "=" * 70)
        print("  SEQUENTIAL RETRY: Merge-conflicted issues")
        print("=" * 70)
        retry_progress = TierProgress(
            tier_num=99,
            description="sequential retry (merge conflicts)",
            total_issues=len(requeued),
        )
        progress.current_tier = retry_progress

        for issue in requeued:
            issue_id = issue["id"]
            result_dict = await _run_tier_sequential(
                [issue], project_dir, model, progress,
            )
            result = result_dict.get(issue_id, {})
            if result.get("status") == "success":
                branch = result.get("branch", _make_branch_name(issue_id))
                mr = await merge_branch(project_dir, branch)
                if mr.success:
                    completed.add(issue_id)
                    progress.completed_issues.add(issue_id)
                    progress.requeued_issues.discard(issue_id)
                    await delete_branch(project_dir, branch)

    # Phase 6: Clean up
    await cleanup_worktrees(project_dir)

    # Final summary
    print_parallel_summary(progress)
    print_progress_summary(project_dir)

    # Check if all done
    if len(completed) >= plan.total_issues:
        print("\nAll issues completed! Run without --parallel to finalize project completion.")
