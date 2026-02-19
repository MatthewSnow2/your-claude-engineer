"""Tests for parallel_progress.py — progress display utilities."""

import json
import time
from pathlib import Path

import pytest

from parallel_progress import (
    ParallelProgress,
    TierProgress,
    WorkerState,
    load_worker_result,
)


# --- WorkerState tests ---


class TestWorkerState:
    def test_defaults(self) -> None:
        ws = WorkerState(worker_index=0, issue_id="T-1", issue_title="Test")
        assert ws.status == "starting"
        assert ws.is_active is True
        assert ws.end_time is None

    def test_elapsed_increases(self) -> None:
        ws = WorkerState(
            worker_index=0,
            issue_id="T-1",
            issue_title="Test",
            start_time=time.monotonic() - 5,
        )
        assert ws.elapsed >= 5.0

    def test_elapsed_fixed_when_ended(self) -> None:
        start = time.monotonic() - 10
        ws = WorkerState(
            worker_index=0,
            issue_id="T-1",
            issue_title="Test",
            start_time=start,
            end_time=start + 5,
        )
        assert abs(ws.elapsed - 5.0) < 0.1

    def test_elapsed_str_format(self) -> None:
        ws = WorkerState(
            worker_index=0,
            issue_id="T-1",
            issue_title="Test",
            start_time=time.monotonic() - 125,  # 2m 5s
        )
        s = ws.elapsed_str
        assert "m" in s and "s" in s

    def test_is_active_for_terminal_states(self) -> None:
        for status in ("done", "failed", "merge_conflict"):
            ws = WorkerState(worker_index=0, issue_id="T-1", issue_title="Test", status=status)
            assert ws.is_active is False

    def test_is_active_for_running_states(self) -> None:
        for status in ("starting", "coding", "code_review", "qa", "github"):
            ws = WorkerState(worker_index=0, issue_id="T-1", issue_title="Test", status=status)
            assert ws.is_active is True


# --- TierProgress tests ---


class TestTierProgress:
    def test_defaults(self) -> None:
        tp = TierProgress(tier_num=1, description="test", total_issues=5)
        assert tp.completed == 0
        assert tp.failed == 0
        assert tp.active_workers == 0

    def test_completed_count(self) -> None:
        tp = TierProgress(tier_num=1, description="test", total_issues=5)
        tp.completed_ids.add("T-1")
        tp.completed_ids.add("T-2")
        assert tp.completed == 2

    def test_active_workers_count(self) -> None:
        tp = TierProgress(tier_num=1, description="test", total_issues=5)
        tp.workers[0] = WorkerState(0, "T-1", "Test1", status="coding")
        tp.workers[1] = WorkerState(1, "T-2", "Test2", status="done")
        tp.workers[2] = WorkerState(2, "T-3", "Test3", status="qa")
        assert tp.active_workers == 2


# --- ParallelProgress tests ---


class TestParallelProgress:
    def test_overall_completed(self) -> None:
        pp = ParallelProgress(total_issues=10)
        pp.completed_issues.update({"T-1", "T-2", "T-3"})
        assert pp.overall_completed == 3

    def test_elapsed_str(self) -> None:
        pp = ParallelProgress(
            total_issues=10,
            start_time=time.monotonic() - 3661,  # 1h 1m 1s
        )
        s = pp.elapsed_str
        assert "h" in s  # Should show hours


# --- load_worker_result tests ---


class TestLoadWorkerResult:
    def test_load_valid_result(self, tmp_path: Path) -> None:
        result_data = {
            "issue_id": "T-1",
            "status": "success",
            "branch": "parallel/T-1",
            "files_changed": ["src/app.py"],
            "duration_seconds": 120.5,
            "error": "",
        }
        result_path = tmp_path / "T-1.json"
        result_path.write_text(json.dumps(result_data))

        loaded = load_worker_result(result_path)
        assert loaded is not None
        assert loaded["issue_id"] == "T-1"
        assert loaded["status"] == "success"
        assert loaded["duration_seconds"] == 120.5

    def test_load_missing_file(self, tmp_path: Path) -> None:
        result = load_worker_result(tmp_path / "nonexistent.json")
        assert result is None

    def test_load_corrupted_json(self, tmp_path: Path) -> None:
        result_path = tmp_path / "bad.json"
        result_path.write_text("not valid json{{{")
        result = load_worker_result(result_path)
        assert result is None

    def test_load_error_result(self, tmp_path: Path) -> None:
        result_data = {
            "issue_id": "T-2",
            "status": "error",
            "branch": "parallel/T-2",
            "files_changed": [],
            "duration_seconds": 5.0,
            "error": "SDK connection failed",
        }
        result_path = tmp_path / "T-2.json"
        result_path.write_text(json.dumps(result_data))

        loaded = load_worker_result(result_path)
        assert loaded is not None
        assert loaded["status"] == "error"
        assert "SDK" in loaded["error"]
