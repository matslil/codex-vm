"""Job lifecycle management independent of the HTTP transport."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

from .models import Artifact, InputSpec, JobSpec, JobState, ValidationError
from .runtime import EnvironmentRuntime
from .security import receive_verified, sha256_file
from .store import JobStore


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


class JobManager:
    def __init__(
        self, store: JobStore, runtime: EnvironmentRuntime, maximum_input_bytes: int
    ) -> None:
        self.store = store
        self.runtime = runtime
        self.maximum_input_bytes = maximum_input_bytes
        self._specs: dict[str, JobSpec] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.RLock()

    def create(self, spec: JobSpec) -> dict[str, Any]:
        with self._lock:
            active = [
                job_id
                for job_id in self._specs
                if not JobState(self.store.read(job_id)["state"]).terminal
            ]
            if active:
                raise RuntimeError("worker already has an active job")
            state = self.store.create(spec)
            self._specs[spec.job_id] = spec
            return self._public(state)

    def upload(
        self, job_id: str, name: str, stream: BinaryIO, content_length: int
    ) -> dict[str, Any]:
        spec = self._get_spec(job_id)
        item = self._get_input(spec, name)
        if content_length != item.size:
            raise ValidationError("Content-Length does not match declared input size")
        state = self.store.read(job_id)
        if JobState(state["state"]) not in {JobState.CREATED, JobState.RECEIVING_INPUT}:
            raise RuntimeError("job no longer accepts input")
        destination = self.store.input_dir(job_id) / name
        receive_verified(
            stream,
            destination,
            expected_size=item.size,
            expected_digest=item.sha256,
            maximum_size=self.maximum_input_bytes,
        )
        return self._public(self.store.mark_input(job_id, name))

    def start(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            spec = self._get_spec(job_id)
            state = self.store.read(job_id)
            expected = {item.name for item in spec.inputs}
            received = set(state["received_inputs"])
            if expected != received:
                missing = ", ".join(sorted(expected - received))
                raise ValidationError(f"job inputs are incomplete: {missing}")
            if JobState(state["state"]) not in {JobState.CREATED, JobState.RECEIVING_INPUT}:
                raise RuntimeError("job has already started")
            thread = threading.Thread(target=self._execute, args=(spec,), daemon=True)
            self._threads[job_id] = thread
            state = self.store.update(
                job_id,
                state=JobState.PREPARING_ENVIRONMENT,
                phase="pulling-environment",
                started_at=timestamp(),
            )
            thread.start()
            return self._public(state)

    def status(self, job_id: str) -> dict[str, Any]:
        self._get_spec(job_id)
        return self._public(self.store.read(job_id))

    def cancel(self, job_id: str) -> dict[str, Any]:
        state = self.store.read(job_id)
        if not JobState(state["state"]).terminal:
            self.runtime.cancel(job_id)
            state = self.store.update(job_id, phase="cancelling")
        return self._public(state)

    def artifact_path(self, job_id: str, name: str) -> Path:
        state = self.store.read(job_id)
        artifact = next((item for item in state["artifacts"] if item["name"] == name), None)
        if artifact is None:
            raise FileNotFoundError(name)
        path = self.store.output_dir(job_id) / str(artifact["filename"])
        if not path.is_file():
            raise FileNotFoundError(name)
        return path

    def _execute(self, spec: JobSpec) -> None:
        try:
            self.runtime.prepare(spec)
            self.store.update(spec.job_id, state=JobState.RUNNING, phase="environment-running")
            result = self.runtime.run(
                spec,
                self.store.job_root(spec.job_id),
                self.store.logs_dir(spec.job_id) / "stdout.log",
                self.store.logs_dir(spec.job_id) / "stderr.log",
            )
            self.store.update(
                spec.job_id,
                state=JobState.COLLECTING_RESULTS,
                phase="collecting-results",
            )
            artifacts = self._collect_artifacts(spec.job_id)
            self.store.set_artifacts(spec.job_id, artifacts)
            if result.cancelled:
                final = JobState.CANCELLED
            elif result.timed_out:
                final = JobState.TIMED_OUT
            elif result.exit_code == 0:
                final = JobState.SUCCEEDED
            else:
                final = JobState.FAILED
            self.store.update(
                spec.job_id,
                state=final,
                phase="complete",
                exit_code=result.exit_code,
                finished_at=timestamp(),
            )
        except Exception as error:  # The durable state is the worker's failure boundary.
            self.store.update(
                spec.job_id,
                state=JobState.FAILED,
                phase="worker-error",
                error=f"{type(error).__name__}: {error}",
                finished_at=timestamp(),
            )

    def _collect_artifacts(self, job_id: str) -> list[Artifact]:
        output = self.store.output_dir(job_id)
        logs = self.store.logs_dir(job_id)
        for log in logs.iterdir():
            if log.is_file():
                target = output / log.name
                target.write_bytes(log.read_bytes())
        artifacts: list[Artifact] = []
        for path in sorted(output.iterdir()):
            if path.is_file() and not path.is_symlink():
                artifacts.append(
                    Artifact(
                        name=path.name,
                        kind="log" if path.suffix == ".log" else "result",
                        filename=path.name,
                        size=path.stat().st_size,
                        sha256=sha256_file(path),
                    )
                )
        return artifacts

    def _get_spec(self, job_id: str) -> JobSpec:
        try:
            return self._specs[job_id]
        except KeyError as error:
            raise FileNotFoundError(job_id) from error

    @staticmethod
    def _get_input(spec: JobSpec, name: str) -> InputSpec:
        try:
            return next(item for item in spec.inputs if item.name == name)
        except StopIteration as error:
            raise FileNotFoundError(name) from error

    @staticmethod
    def _public(state: dict[str, Any]) -> dict[str, Any]:
        result = dict(state)
        result.pop("spec", None)
        for artifact in result.get("artifacts", []):
            artifact["url"] = f"/v1/jobs/{state['job_id']}/artifacts/{artifact['name']}"
        return result
