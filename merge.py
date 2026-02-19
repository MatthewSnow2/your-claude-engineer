"""
Git Worktree & Merge Utilities
==============================

Handles worktree lifecycle and branch merging for parallel execution.
Each parallel worker gets its own worktree (filesystem directory) so
concurrent agents don't conflict on file writes.

Worktrees share the same .git object store, so they're lightweight on disk.
"""

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


WORKERS_DIR_NAME: str = ".workers"
RESULTS_DIR_NAME: str = "results"


@dataclass
class MergeResult:
    """Result of merging a branch into the main branch."""

    branch: str
    success: bool
    conflict: bool = False
    error: str = ""


async def _run_git(
    cwd: Path,
    *args: str,
) -> tuple[int, str, str]:
    """
    Run a git command and return (returncode, stdout, stderr).

    Args:
        cwd: Working directory for the git command.
        *args: Git subcommand and arguments.

    Returns:
        Tuple of (returncode, stdout, stderr).
    """
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await proc.communicate()
    return (
        proc.returncode or 0,
        stdout_bytes.decode().strip(),
        stderr_bytes.decode().strip(),
    )


def get_workers_dir(project_dir: Path) -> Path:
    """Get the .workers directory path for a project."""
    return project_dir / WORKERS_DIR_NAME


def get_results_dir(project_dir: Path) -> Path:
    """Get the results directory path for a project."""
    return get_workers_dir(project_dir) / RESULTS_DIR_NAME


def get_worktree_dir(project_dir: Path, worker_index: int) -> Path:
    """Get the worktree directory for a specific worker."""
    return get_workers_dir(project_dir) / f"w{worker_index}"


async def create_worktree(
    project_dir: Path,
    worktree_dir: Path,
    branch: str,
) -> bool:
    """
    Create a git worktree for isolated parallel work.

    Creates a new branch and worktree at the specified directory.
    The worktree starts from the current HEAD of the main repo.

    Args:
        project_dir: Main project git repository.
        worktree_dir: Directory for the new worktree.
        branch: Branch name for this worktree.

    Returns:
        True if worktree was created successfully.
    """
    # Ensure parent directory exists
    worktree_dir.parent.mkdir(parents=True, exist_ok=True)

    # Clean up if worktree dir already exists (stale from previous run)
    if worktree_dir.exists():
        await remove_worktree(project_dir, worktree_dir)

    # Delete the branch if it already exists (stale from previous run)
    await _run_git(project_dir, "branch", "-D", branch)

    # Create worktree with new branch from current HEAD
    rc, stdout, stderr = await _run_git(
        project_dir,
        "worktree", "add", "-b", branch, str(worktree_dir),
    )

    if rc != 0:
        print(f"  [merge] Failed to create worktree: {stderr}")
        return False

    print(f"  [merge] Created worktree: {worktree_dir.name} → branch {branch}")
    return True


async def remove_worktree(
    project_dir: Path,
    worktree_dir: Path,
) -> bool:
    """
    Remove a git worktree.

    Args:
        project_dir: Main project git repository.
        worktree_dir: Directory of the worktree to remove.

    Returns:
        True if worktree was removed successfully.
    """
    if not worktree_dir.exists():
        return True

    # Try git worktree remove first
    rc, _, stderr = await _run_git(
        project_dir,
        "worktree", "remove", "--force", str(worktree_dir),
    )

    if rc != 0:
        # Fallback: manually remove directory and prune
        try:
            shutil.rmtree(worktree_dir)
        except OSError as e:
            print(f"  [merge] Warning: Could not remove {worktree_dir}: {e}")
            return False

        await _run_git(project_dir, "worktree", "prune")

    return True


async def merge_branch(
    project_dir: Path,
    branch: str,
) -> MergeResult:
    """
    Merge a worker branch into the current branch (main/HEAD).

    Uses --no-ff to preserve branch history for traceability.
    If merge conflicts occur, the merge is aborted and the result
    indicates a conflict for re-queuing.

    Args:
        project_dir: Main project git repository.
        branch: Branch name to merge.

    Returns:
        MergeResult with success/conflict status.
    """
    rc, stdout, stderr = await _run_git(
        project_dir,
        "merge", "--no-ff", "-m", f"Merge parallel branch: {branch}",
        branch,
    )

    if rc == 0:
        print(f"  [merge] Merged {branch} successfully")
        return MergeResult(branch=branch, success=True)

    # Check for merge conflict
    if "conflict" in stderr.lower() or "conflict" in stdout.lower():
        print(f"  [merge] Conflict merging {branch} — aborting and re-queuing")
        await _run_git(project_dir, "merge", "--abort")
        return MergeResult(branch=branch, success=False, conflict=True)

    # Other merge failure
    print(f"  [merge] Failed to merge {branch}: {stderr}")
    await _run_git(project_dir, "merge", "--abort")
    return MergeResult(branch=branch, success=False, error=stderr)


async def delete_branch(project_dir: Path, branch: str) -> None:
    """Delete a local branch after successful merge."""
    await _run_git(project_dir, "branch", "-d", branch)


async def cleanup_worktrees(project_dir: Path) -> None:
    """
    Remove all worker worktrees and the .workers directory.

    Safe to call even if no worktrees exist.
    """
    workers_dir = get_workers_dir(project_dir)
    if not workers_dir.exists():
        return

    # List and remove all worktrees
    rc, stdout, _ = await _run_git(project_dir, "worktree", "list", "--porcelain")
    if rc == 0:
        for line in stdout.splitlines():
            if line.startswith("worktree ") and WORKERS_DIR_NAME in line:
                wt_path = Path(line.split(" ", 1)[1])
                await remove_worktree(project_dir, wt_path)

    # Prune stale worktree references
    await _run_git(project_dir, "worktree", "prune")

    # Remove workers directory
    try:
        shutil.rmtree(workers_dir)
        print(f"  [merge] Cleaned up {workers_dir}")
    except OSError:
        pass


async def ensure_git_initialized(project_dir: Path) -> bool:
    """
    Check that project_dir is a git repository.

    Returns:
        True if project_dir has a .git directory or is a worktree.
    """
    rc, _, _ = await _run_git(project_dir, "rev-parse", "--git-dir")
    return rc == 0
