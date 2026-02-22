#!/usr/bin/env python3
"""
Queue Runner
============

Multi-project job queue for yce-harness. Feeds app specs to
autonomous_agent_demo.py sequentially, enabling Metroplex (the L5
autonomy layer) to queue multiple builds.

Usage:
    python queue_runner.py add prompts/app_spec.txt --id metroplex --model haiku
    python queue_runner.py add spec.txt --id my-app --model sonnet --parallel --max-workers 3
    python queue_runner.py start
    python queue_runner.py start --dry-run
    python queue_runner.py status
    python queue_runner.py status --id metroplex
    python queue_runner.py status --json
"""

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


# --- Constants ---

HARNESS_DIR: Path = Path(__file__).parent
QUEUE_DIR: Path = HARNESS_DIR / "data"
QUEUE_FILE: Path = QUEUE_DIR / "queue.json"
APP_SPEC_PATH: Path = HARNESS_DIR / "prompts" / "app_spec.txt"


# --- Models ---


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    interrupted = "interrupted"


class QueueJob(BaseModel):
    id: str
    spec_path: str
    model: str = "haiku"
    max_iterations: int = 20
    parallel: bool = False
    max_workers: int = 2
    status: JobStatus = JobStatus.pending
    project_dir: str | None = None
    exit_code: int | None = None
    error: str | None = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None


class QueueState(BaseModel):
    version: int = 1
    jobs: list[QueueJob] = Field(default_factory=list)


# --- Persistence ---


def load_queue() -> QueueState:
    """Load queue state from disk, or return empty state."""
    if not QUEUE_FILE.exists():
        return QueueState()
    data = json.loads(QUEUE_FILE.read_text())
    return QueueState.model_validate(data)


def save_queue(state: QueueState) -> None:
    """Save queue state to disk."""
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    QUEUE_FILE.write_text(
        json.dumps(state.model_dump(mode="json"), indent=2) + "\n"
    )


# --- Helpers ---


def _get_processable_jobs(state: QueueState) -> list[QueueJob]:
    """Return jobs eligible for processing (pending, interrupted, or stale running)."""
    return [
        job
        for job in state.jobs
        if job.status in (JobStatus.pending, JobStatus.interrupted, JobStatus.running)
    ]


def _build_command(job: QueueJob) -> list[str]:
    """Build the subprocess command list for autonomous_agent_demo.py."""
    cmd = [
        sys.executable,
        str(HARNESS_DIR / "autonomous_agent_demo.py"),
        "--project-dir",
        job.id,
        "--model",
        job.model,
        "--max-iterations",
        str(job.max_iterations),
    ]
    if job.parallel:
        cmd.append("--parallel")
        cmd.extend(["--max-workers", str(job.max_workers)])
    return cmd


def _run_job(job: QueueJob, dry_run: bool = False) -> None:
    """
    Execute a single queue job.

    Swaps the app spec into prompts/app_spec.txt before launch,
    restores the original afterward.
    """
    spec_source = Path(job.spec_path)
    if not spec_source.is_absolute():
        spec_source = HARNESS_DIR / spec_source

    if not spec_source.exists():
        job.status = JobStatus.failed
        job.error = f"Spec file not found: {spec_source}"
        return

    # Resolve project dir
    job.project_dir = str(HARNESS_DIR / "generations" / job.id)

    cmd = _build_command(job)

    if dry_run:
        print(f"  [dry-run] Would execute: {' '.join(cmd)}")
        print(f"  [dry-run] Spec: {spec_source}")
        print(f"  [dry-run] Project dir: {job.project_dir}")
        return

    # Spec swap: backup → copy job spec → run → restore
    backup_path = APP_SPEC_PATH.with_suffix(".txt.bak")
    spec_swapped = False

    try:
        # Only swap if the job spec differs from the default location
        if spec_source.resolve() != APP_SPEC_PATH.resolve():
            if APP_SPEC_PATH.exists():
                shutil.copy2(APP_SPEC_PATH, backup_path)
            shutil.copy2(spec_source, APP_SPEC_PATH)
            spec_swapped = True

        job.status = JobStatus.running
        job.started_at = datetime.now(timezone.utc).isoformat()

        print(f"\n{'=' * 70}")
        print(f"  QUEUE: Starting job '{job.id}'")
        print(f"  Model: {job.model} | Parallel: {job.parallel} | Spec: {spec_source.name}")
        print(f"{'=' * 70}\n")

        start_time = time.monotonic()

        result = subprocess.run(
            cmd,
            cwd=str(HARNESS_DIR),
        )

        elapsed = time.monotonic() - start_time
        job.exit_code = result.returncode
        job.duration_seconds = round(elapsed, 1)
        job.completed_at = datetime.now(timezone.utc).isoformat()

        if result.returncode == 0:
            job.status = JobStatus.completed
        elif result.returncode == 130:
            job.status = JobStatus.interrupted
        else:
            job.status = JobStatus.failed
            job.error = f"Process exited with code {result.returncode}"

    except KeyboardInterrupt:
        job.status = JobStatus.interrupted
        job.completed_at = datetime.now(timezone.utc).isoformat()
        raise
    except Exception as e:
        job.status = JobStatus.failed
        job.error = str(e)
        job.completed_at = datetime.now(timezone.utc).isoformat()
    finally:
        # Restore original spec
        if spec_swapped and backup_path.exists():
            shutil.move(str(backup_path), str(APP_SPEC_PATH))
        elif spec_swapped and not backup_path.exists():
            # Original didn't exist; remove the swapped copy
            APP_SPEC_PATH.unlink(missing_ok=True)


# --- CLI Commands ---


def cmd_add(args: argparse.Namespace) -> int:
    """Add a job to the queue."""
    spec = Path(args.spec_path)
    if not spec.is_absolute():
        spec = HARNESS_DIR / spec

    if not spec.exists():
        print(f"Error: Spec file not found: {spec}")
        return 1

    state = load_queue()

    # Check for duplicate ID
    existing_ids = {job.id for job in state.jobs}
    if args.id in existing_ids:
        print(f"Error: Job with id '{args.id}' already exists")
        print("Use a different --id or remove the existing job from data/queue.json")
        return 1

    job = QueueJob(
        id=args.id,
        spec_path=args.spec_path,
        model=args.model,
        max_iterations=args.max_iterations,
        parallel=args.parallel,
        max_workers=args.max_workers,
    )

    state.jobs.append(job)
    save_queue(state)

    print(f"Added job '{job.id}' to queue")
    print(f"  Spec: {args.spec_path}")
    print(f"  Model: {job.model} | Iterations: {job.max_iterations} | Parallel: {job.parallel}")
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    """Process the queue sequentially."""
    state = load_queue()
    processable = _get_processable_jobs(state)

    if not processable:
        print("Queue is empty or all jobs are completed/failed.")
        return 0

    print(f"Processing {len(processable)} job(s)...\n")

    interrupted = False
    for job in processable:
        try:
            _run_job(job, dry_run=args.dry_run)
        except KeyboardInterrupt:
            print(f"\n\nInterrupted during job '{job.id}'")
            interrupted = True
            break
        finally:
            if not args.dry_run:
                save_queue(state)

    # Print summary
    if not args.dry_run:
        completed = sum(1 for j in state.jobs if j.status == JobStatus.completed)
        failed = sum(1 for j in state.jobs if j.status == JobStatus.failed)
        pending = sum(1 for j in state.jobs if j.status == JobStatus.pending)
        inter = sum(1 for j in state.jobs if j.status == JobStatus.interrupted)

        print(f"\n{'=' * 70}")
        print(f"  QUEUE SUMMARY")
        print(f"  Completed: {completed} | Failed: {failed} | Pending: {pending} | Interrupted: {inter}")
        print(f"{'=' * 70}")

    return 130 if interrupted else 0


def cmd_status(args: argparse.Namespace) -> int:
    """Display queue status."""
    state = load_queue()

    if not state.jobs:
        if args.json:
            print(json.dumps({"jobs": [], "summary": {}}, indent=2))
        else:
            print("Queue is empty.")
        return 0

    # Filter by ID if provided
    jobs = state.jobs
    if args.id:
        jobs = [j for j in jobs if j.id == args.id]
        if not jobs:
            print(f"No job found with id '{args.id}'")
            return 1

    if args.json:
        output = {
            "jobs": [j.model_dump(mode="json") for j in jobs],
            "summary": {
                "total": len(state.jobs),
                "pending": sum(1 for j in state.jobs if j.status == JobStatus.pending),
                "running": sum(1 for j in state.jobs if j.status == JobStatus.running),
                "completed": sum(1 for j in state.jobs if j.status == JobStatus.completed),
                "failed": sum(1 for j in state.jobs if j.status == JobStatus.failed),
                "interrupted": sum(1 for j in state.jobs if j.status == JobStatus.interrupted),
            },
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"Queue: {len(state.jobs)} job(s)\n")
        for job in jobs:
            status_icon = {
                JobStatus.pending: " ",
                JobStatus.running: "~",
                JobStatus.completed: "+",
                JobStatus.failed: "x",
                JobStatus.interrupted: "!",
            }.get(job.status, "?")
            duration = f" ({job.duration_seconds}s)" if job.duration_seconds else ""
            error = f" — {job.error}" if job.error else ""
            print(f"  [{status_icon}] {job.id}: {job.status.value}{duration}{error}")
            print(f"      spec={job.spec_path} model={job.model} parallel={job.parallel}")

    return 0


# --- Argument Parsing ---


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="yce-harness multi-project job queue",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python queue_runner.py add prompts/app_spec.txt --id metroplex --model haiku
  python queue_runner.py add spec.txt --id my-app --model sonnet --parallel --max-workers 3
  python queue_runner.py start
  python queue_runner.py start --dry-run
  python queue_runner.py status
  python queue_runner.py status --id metroplex --json
        """,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- add ---
    add_parser = subparsers.add_parser("add", help="Add a job to the queue")
    add_parser.add_argument(
        "spec_path",
        type=str,
        help="Path to the app spec file",
    )
    add_parser.add_argument(
        "--id",
        type=str,
        required=True,
        help="Unique job identifier (used as project directory name)",
    )
    add_parser.add_argument(
        "--model",
        type=str,
        choices=["haiku", "sonnet", "opus"],
        default="haiku",
        help="Orchestrator model (default: haiku)",
    )
    add_parser.add_argument(
        "--max-iterations",
        type=int,
        default=20,
        help="Maximum agent iterations (default: 20)",
    )
    add_parser.add_argument(
        "--parallel",
        action="store_true",
        default=False,
        help="Enable parallel execution mode",
    )
    add_parser.add_argument(
        "--max-workers",
        type=int,
        default=2,
        help="Max concurrent workers in parallel mode (default: 2)",
    )

    # --- start ---
    start_parser = subparsers.add_parser("start", help="Process the queue")
    start_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show what would run without executing",
    )

    # --- status ---
    status_parser = subparsers.add_parser("status", help="Show queue status")
    status_parser.add_argument(
        "--id",
        type=str,
        default=None,
        help="Filter by job ID",
    )
    status_parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output machine-parseable JSON",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "add":
        return cmd_add(args)
    elif args.command == "start":
        return cmd_start(args)
    elif args.command == "status":
        return cmd_status(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
