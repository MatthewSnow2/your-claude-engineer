"""Tests for merge.py — git worktree and merge utilities."""

import asyncio
import os
from pathlib import Path

import pytest
import pytest_asyncio

from merge import (
    MergeResult,
    WORKERS_DIR_NAME,
    cleanup_worktrees,
    create_worktree,
    delete_branch,
    ensure_git_initialized,
    get_results_dir,
    get_workers_dir,
    get_worktree_dir,
    merge_branch,
    remove_worktree,
    _run_git,
)


# --- Helpers ---


async def _init_repo(path: Path) -> None:
    """Initialize a git repo with an initial commit."""
    await _run_git(path, "init")
    await _run_git(path, "config", "user.email", "test@test.com")
    await _run_git(path, "config", "user.name", "Test")
    # Create initial commit (git worktree requires at least one commit)
    (path / "README.md").write_text("# Test Project\n")
    await _run_git(path, "add", ".")
    await _run_git(path, "commit", "-m", "Initial commit")


# --- Fixtures ---


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository with initial commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    asyncio.get_event_loop().run_until_complete(_init_repo(repo))
    return repo


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# --- Path helper tests ---


class TestPathHelpers:
    def test_get_workers_dir(self, tmp_path: Path) -> None:
        result = get_workers_dir(tmp_path)
        assert result == tmp_path / WORKERS_DIR_NAME

    def test_get_results_dir(self, tmp_path: Path) -> None:
        result = get_results_dir(tmp_path)
        assert result == tmp_path / WORKERS_DIR_NAME / "results"

    def test_get_worktree_dir(self, tmp_path: Path) -> None:
        result = get_worktree_dir(tmp_path, 0)
        assert result == tmp_path / WORKERS_DIR_NAME / "w0"
        result2 = get_worktree_dir(tmp_path, 2)
        assert result2 == tmp_path / WORKERS_DIR_NAME / "w2"


# --- _run_git tests ---


class TestRunGit:
    def test_successful_command(self, tmp_repo: Path) -> None:
        rc, stdout, stderr = asyncio.get_event_loop().run_until_complete(
            _run_git(tmp_repo, "status")
        )
        assert rc == 0

    def test_failed_command(self, tmp_repo: Path) -> None:
        rc, stdout, stderr = asyncio.get_event_loop().run_until_complete(
            _run_git(tmp_repo, "checkout", "nonexistent-branch")
        )
        assert rc != 0


# --- ensure_git_initialized tests ---


class TestEnsureGitInitialized:
    def test_valid_repo(self, tmp_repo: Path) -> None:
        result = asyncio.get_event_loop().run_until_complete(
            ensure_git_initialized(tmp_repo)
        )
        assert result is True

    def test_not_a_repo(self, tmp_path: Path) -> None:
        result = asyncio.get_event_loop().run_until_complete(
            ensure_git_initialized(tmp_path)
        )
        assert result is False


# --- Worktree lifecycle tests ---


class TestWorktreeLifecycle:
    def test_create_worktree(self, tmp_repo: Path) -> None:
        wt_dir = tmp_repo / ".workers" / "w0"
        result = asyncio.get_event_loop().run_until_complete(
            create_worktree(tmp_repo, wt_dir, "test-branch")
        )
        assert result is True
        assert wt_dir.exists()
        assert (wt_dir / "README.md").exists()  # File from initial commit

    def test_create_worktree_already_exists(self, tmp_repo: Path) -> None:
        """Creating a worktree when the dir already exists should clean up and recreate."""
        wt_dir = tmp_repo / ".workers" / "w0"
        # Create first
        asyncio.get_event_loop().run_until_complete(
            create_worktree(tmp_repo, wt_dir, "branch-1")
        )
        # Clean up the first one
        asyncio.get_event_loop().run_until_complete(
            remove_worktree(tmp_repo, wt_dir)
        )
        # Create second with same dir but different branch
        result = asyncio.get_event_loop().run_until_complete(
            create_worktree(tmp_repo, wt_dir, "branch-2")
        )
        assert result is True
        assert wt_dir.exists()

    def test_remove_worktree(self, tmp_repo: Path) -> None:
        wt_dir = tmp_repo / ".workers" / "w0"
        asyncio.get_event_loop().run_until_complete(
            create_worktree(tmp_repo, wt_dir, "test-branch")
        )
        result = asyncio.get_event_loop().run_until_complete(
            remove_worktree(tmp_repo, wt_dir)
        )
        assert result is True
        assert not wt_dir.exists()

    def test_remove_nonexistent_worktree(self, tmp_repo: Path) -> None:
        wt_dir = tmp_repo / ".workers" / "w99"
        result = asyncio.get_event_loop().run_until_complete(
            remove_worktree(tmp_repo, wt_dir)
        )
        assert result is True  # No error on non-existent

    def test_cleanup_worktrees(self, tmp_repo: Path) -> None:
        # Create multiple worktrees
        for i in range(3):
            wt_dir = tmp_repo / ".workers" / f"w{i}"
            asyncio.get_event_loop().run_until_complete(
                create_worktree(tmp_repo, wt_dir, f"branch-{i}")
            )
        assert (tmp_repo / ".workers").exists()

        # Cleanup all
        asyncio.get_event_loop().run_until_complete(
            cleanup_worktrees(tmp_repo)
        )
        assert not (tmp_repo / ".workers").exists()

    def test_cleanup_no_worktrees(self, tmp_repo: Path) -> None:
        """Cleanup should not error when no worktrees exist."""
        asyncio.get_event_loop().run_until_complete(
            cleanup_worktrees(tmp_repo)
        )
        # Should not raise


# --- Merge tests ---


class TestMergeBranch:
    def test_merge_success(self, tmp_repo: Path) -> None:
        """Create a worktree, make changes, merge back."""
        wt_dir = tmp_repo / ".workers" / "w0"
        branch = "test-feature"

        # Create worktree
        asyncio.get_event_loop().run_until_complete(
            create_worktree(tmp_repo, wt_dir, branch)
        )

        # Make a change in the worktree
        (wt_dir / "new_file.txt").write_text("hello from worktree\n")
        asyncio.get_event_loop().run_until_complete(
            _run_git(wt_dir, "add", ".")
        )
        asyncio.get_event_loop().run_until_complete(
            _run_git(wt_dir, "commit", "-m", "Add new file")
        )

        # Remove worktree before merging
        asyncio.get_event_loop().run_until_complete(
            remove_worktree(tmp_repo, wt_dir)
        )

        # Merge
        result: MergeResult = asyncio.get_event_loop().run_until_complete(
            merge_branch(tmp_repo, branch)
        )
        assert result.success is True
        assert result.conflict is False
        assert (tmp_repo / "new_file.txt").exists()

    def test_merge_conflict(self, tmp_repo: Path) -> None:
        """Create conflicting changes and verify conflict detection."""
        wt_dir = tmp_repo / ".workers" / "w0"
        branch = "conflict-branch"

        # Create worktree
        asyncio.get_event_loop().run_until_complete(
            create_worktree(tmp_repo, wt_dir, branch)
        )

        # Modify README.md in worktree
        (wt_dir / "README.md").write_text("# Modified in worktree\n")
        asyncio.get_event_loop().run_until_complete(
            _run_git(wt_dir, "add", ".")
        )
        asyncio.get_event_loop().run_until_complete(
            _run_git(wt_dir, "commit", "-m", "Modify README in worktree")
        )

        # Also modify README.md in main repo (creates conflict)
        (tmp_repo / "README.md").write_text("# Modified in main\n")
        asyncio.get_event_loop().run_until_complete(
            _run_git(tmp_repo, "add", ".")
        )
        asyncio.get_event_loop().run_until_complete(
            _run_git(tmp_repo, "commit", "-m", "Modify README in main")
        )

        # Remove worktree before merging
        asyncio.get_event_loop().run_until_complete(
            remove_worktree(tmp_repo, wt_dir)
        )

        # Merge should detect conflict
        result: MergeResult = asyncio.get_event_loop().run_until_complete(
            merge_branch(tmp_repo, branch)
        )
        assert result.success is False
        assert result.conflict is True

    def test_merge_nonexistent_branch(self, tmp_repo: Path) -> None:
        result: MergeResult = asyncio.get_event_loop().run_until_complete(
            merge_branch(tmp_repo, "nonexistent-branch")
        )
        assert result.success is False

    def test_delete_branch_after_merge(self, tmp_repo: Path) -> None:
        wt_dir = tmp_repo / ".workers" / "w0"
        branch = "deletable-branch"

        asyncio.get_event_loop().run_until_complete(
            create_worktree(tmp_repo, wt_dir, branch)
        )
        (wt_dir / "file.txt").write_text("content\n")
        asyncio.get_event_loop().run_until_complete(_run_git(wt_dir, "add", "."))
        asyncio.get_event_loop().run_until_complete(_run_git(wt_dir, "commit", "-m", "Add file"))
        asyncio.get_event_loop().run_until_complete(remove_worktree(tmp_repo, wt_dir))
        asyncio.get_event_loop().run_until_complete(merge_branch(tmp_repo, branch))

        # Delete branch
        asyncio.get_event_loop().run_until_complete(delete_branch(tmp_repo, branch))

        # Verify branch is gone
        rc, stdout, _ = asyncio.get_event_loop().run_until_complete(
            _run_git(tmp_repo, "branch", "--list", branch)
        )
        assert branch not in stdout
