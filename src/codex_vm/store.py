"""Durable per-job state beneath a worker-owned root directory."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from .models import Artifact, JobSpec, JobState


class JobStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def job_root(self, job_id: str) -> Path:
        return self.root / job_id

    def input_dir(self, job_id: str) -> Path:
        return self.job_root(job_id) / "input"

    def workspace_dir(self, job_id: str) -> Path:
        return self.job_root(job_id) / "workspace"

    def scratch_dir(self, job_id: str) -> Path:
        return self.job_root(job_id) / "scratch"

    def output_dir(self, job_id: str) -> Path:
        return self.job_root(job_id) / "output"

    def logs_dir(self, job_id: str) -> Path:
        return self.job_root(job_id) / "logs"

    def create(self, spec: JobSpec) -> dict[str, Any]:
        with self._lock:
            root = self.job_root(spec.job_id)
            if root.exists():
                raise FileExistsError(spec.job_id)
            for path in (
                self.input_dir(spec.job_id),
                self.workspace_dir(spec.job_id),
                self.scratch_dir(spec.job_id),
                self.output_dir(spec.job_id),
                self.logs_dir(spec.job_id),
            ):
                path.mkdir(parents=True)
            state: dict[str, Any] = {
                "job_id": spec.job_id,
                "state": JobState.CREATED,
                "phase": "awaiting-input",
                "spec": spec.to_dict(),
                "received_inputs": [],
                "artifacts": [],
                "error": None,
            }
            self._write(root / "state.json", state)
            return state

    def exists(self, job_id: str) -> bool:
        return (self.job_root(job_id) / "state.json").is_file()

    def read(self, job_id: str) -> dict[str, Any]:
        with self._lock, (self.job_root(job_id) / "state.json").open(encoding="utf-8") as stream:
            return dict(json.load(stream))

    def update(self, job_id: str, **changes: Any) -> dict[str, Any]:
        with self._lock:
            state = self.read(job_id)
            state.update(changes)
            self._write(self.job_root(job_id) / "state.json", state)
            return state

    def mark_input(self, job_id: str, name: str) -> dict[str, Any]:
        with self._lock:
            state = self.read(job_id)
            names = set(state["received_inputs"])
            names.add(name)
            state["received_inputs"] = sorted(names)
            state["state"] = JobState.RECEIVING_INPUT
            self._write(self.job_root(job_id) / "state.json", state)
            return state

    def set_artifacts(self, job_id: str, artifacts: list[Artifact]) -> dict[str, Any]:
        return self.update(job_id, artifacts=[artifact.to_dict() for artifact in artifacts])

    @staticmethod
    def _write(path: Path, value: dict[str, Any]) -> None:
        descriptor, temporary_name = tempfile.mkstemp(prefix=".state-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(value, stream, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, path)
        except BaseException:
            Path(temporary_name).unlink(missing_ok=True)
            raise
