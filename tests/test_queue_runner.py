"""Tests for queue_runner.py — multi-project job queue."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add parent dir to path so we can import queue_runner
sys.path.insert(0, str(Path(__file__).parent.parent))

from queue_runner import (
    HARNESS_DIR,
    JobStatus,
    QueueJob,
    QueueState,
    _build_command,
    _get_processable_jobs,
    load_queue,
    save_queue,
)


# --- Fixtures ---


@pytest.fixture
def sample_job() -> QueueJob:
    return QueueJob(
        id="test-app",
        spec_path="prompts/app_spec.txt",
        model="haiku",
    )


@pytest.fixture
def sample_state(sample_job: QueueJob) -> QueueState:
    return QueueState(jobs=[sample_job])


@pytest.fixture
def queue_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect queue persistence to a temp directory."""
    queue_dir = tmp_path / "data"
    queue_dir.mkdir()
    queue_path = queue_dir / "queue.json"
    monkeypatch.setattr("queue_runner.QUEUE_DIR", queue_dir)
    monkeypatch.setattr("queue_runner.QUEUE_FILE", queue_path)
    return queue_path


# --- Model defaults ---


class TestQueueJobDefaults:
    def test_default_status_is_pending(self) -> None:
        job = QueueJob(id="x", spec_path="s.txt")
        assert job.status == JobStatus.pending

    def test_default_model_is_haiku(self) -> None:
        job = QueueJob(id="x", spec_path="s.txt")
        assert job.model == "haiku"

    def test_default_max_iterations(self) -> None:
        job = QueueJob(id="x", spec_path="s.txt")
        assert job.max_iterations == 20

    def test_default_parallel_is_false(self) -> None:
        job = QueueJob(id="x", spec_path="s.txt")
        assert job.parallel is False

    def test_default_max_workers(self) -> None:
        job = QueueJob(id="x", spec_path="s.txt")
        assert job.max_workers == 2

    def test_created_at_is_set(self) -> None:
        job = QueueJob(id="x", spec_path="s.txt")
        assert job.created_at is not None
        assert "T" in job.created_at  # ISO format

    def test_optional_fields_are_none(self) -> None:
        job = QueueJob(id="x", spec_path="s.txt")
        assert job.project_dir is None
        assert job.exit_code is None
        assert job.error is None
        assert job.started_at is None
        assert job.completed_at is None
        assert job.duration_seconds is None


class TestQueueStateDefaults:
    def test_default_version(self) -> None:
        state = QueueState()
        assert state.version == 1

    def test_default_empty_jobs(self) -> None:
        state = QueueState()
        assert state.jobs == []


# --- Serialization round-trips ---


class TestSerialization:
    def test_job_round_trip(self, sample_job: QueueJob) -> None:
        data = sample_job.model_dump(mode="json")
        restored = QueueJob.model_validate(data)
        assert restored.id == sample_job.id
        assert restored.spec_path == sample_job.spec_path
        assert restored.model == sample_job.model
        assert restored.status == sample_job.status

    def test_state_round_trip(self, sample_state: QueueState) -> None:
        data = sample_state.model_dump(mode="json")
        restored = QueueState.model_validate(data)
        assert len(restored.jobs) == 1
        assert restored.jobs[0].id == "test-app"
        assert restored.version == 1

    def test_json_round_trip(self, sample_state: QueueState) -> None:
        json_str = json.dumps(sample_state.model_dump(mode="json"))
        data = json.loads(json_str)
        restored = QueueState.model_validate(data)
        assert restored.jobs[0].id == "test-app"

    def test_persistence_round_trip(
        self, sample_state: QueueState, queue_file: Path
    ) -> None:
        save_queue(sample_state)
        assert queue_file.exists()
        loaded = load_queue()
        assert len(loaded.jobs) == 1
        assert loaded.jobs[0].id == "test-app"

    def test_load_empty_returns_default(self, queue_file: Path) -> None:
        state = load_queue()
        assert state.jobs == []
        assert state.version == 1

    def test_all_statuses_serialize(self) -> None:
        for status in JobStatus:
            job = QueueJob(id="x", spec_path="s.txt", status=status)
            data = job.model_dump(mode="json")
            restored = QueueJob.model_validate(data)
            assert restored.status == status


# --- Processable job filtering ---


class TestProcessableJobs:
    def test_pending_is_processable(self) -> None:
        state = QueueState(
            jobs=[QueueJob(id="a", spec_path="s.txt", status=JobStatus.pending)]
        )
        assert len(_get_processable_jobs(state)) == 1

    def test_interrupted_is_processable(self) -> None:
        state = QueueState(
            jobs=[QueueJob(id="a", spec_path="s.txt", status=JobStatus.interrupted)]
        )
        assert len(_get_processable_jobs(state)) == 1

    def test_running_is_processable(self) -> None:
        """Stale 'running' jobs (from killed process) should be re-processable."""
        state = QueueState(
            jobs=[QueueJob(id="a", spec_path="s.txt", status=JobStatus.running)]
        )
        assert len(_get_processable_jobs(state)) == 1

    def test_completed_is_not_processable(self) -> None:
        state = QueueState(
            jobs=[QueueJob(id="a", spec_path="s.txt", status=JobStatus.completed)]
        )
        assert len(_get_processable_jobs(state)) == 0

    def test_failed_is_not_processable(self) -> None:
        state = QueueState(
            jobs=[QueueJob(id="a", spec_path="s.txt", status=JobStatus.failed)]
        )
        assert len(_get_processable_jobs(state)) == 0

    def test_mixed_statuses(self) -> None:
        state = QueueState(
            jobs=[
                QueueJob(id="a", spec_path="s.txt", status=JobStatus.completed),
                QueueJob(id="b", spec_path="s.txt", status=JobStatus.pending),
                QueueJob(id="c", spec_path="s.txt", status=JobStatus.failed),
                QueueJob(id="d", spec_path="s.txt", status=JobStatus.interrupted),
            ]
        )
        processable = _get_processable_jobs(state)
        ids = {j.id for j in processable}
        assert ids == {"b", "d"}

    def test_empty_queue(self) -> None:
        state = QueueState()
        assert _get_processable_jobs(state) == []


# --- Command building ---


class TestBuildCommand:
    def test_sequential_command(self) -> None:
        job = QueueJob(
            id="my-app",
            spec_path="spec.txt",
            model="haiku",
            max_iterations=10,
        )
        cmd = _build_command(job)
        assert sys.executable in cmd[0]
        assert "autonomous_agent_demo.py" in cmd[1]
        assert "--project-dir" in cmd
        assert "my-app" in cmd
        assert "--model" in cmd
        assert "haiku" in cmd
        assert "--max-iterations" in cmd
        assert "10" in cmd
        assert "--parallel" not in cmd

    def test_parallel_command(self) -> None:
        job = QueueJob(
            id="my-app",
            spec_path="spec.txt",
            model="sonnet",
            parallel=True,
            max_workers=3,
        )
        cmd = _build_command(job)
        assert "--parallel" in cmd
        assert "--max-workers" in cmd
        assert "3" in cmd
        assert "sonnet" in cmd

    def test_opus_model(self) -> None:
        job = QueueJob(id="x", spec_path="s.txt", model="opus")
        cmd = _build_command(job)
        assert "opus" in cmd

    def test_default_iterations_in_command(self) -> None:
        job = QueueJob(id="x", spec_path="s.txt")
        cmd = _build_command(job)
        assert "20" in cmd


# --- Duplicate ID detection ---


class TestDuplicateId:
    def test_duplicate_detected(self, queue_file: Path) -> None:
        state = QueueState(
            jobs=[QueueJob(id="dup", spec_path="s.txt")]
        )
        save_queue(state)

        loaded = load_queue()
        existing_ids = {job.id for job in loaded.jobs}
        assert "dup" in existing_ids

    def test_unique_id_allowed(self, queue_file: Path) -> None:
        state = QueueState(
            jobs=[QueueJob(id="existing", spec_path="s.txt")]
        )
        save_queue(state)

        loaded = load_queue()
        existing_ids = {job.id for job in loaded.jobs}
        assert "new-id" not in existing_ids


# --- JobStatus enum ---


class TestJobStatus:
    def test_all_statuses_exist(self) -> None:
        expected = {"pending", "running", "completed", "failed", "interrupted"}
        assert {s.value for s in JobStatus} == expected

    def test_string_enum(self) -> None:
        assert JobStatus.pending == "pending"
        assert JobStatus.completed.value == "completed"
