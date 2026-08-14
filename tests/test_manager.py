from __future__ import annotations

import tempfile
import time
import unittest
from io import BytesIO
from pathlib import Path

from codex_vm.manager import JobManager
from codex_vm.models import JobSpec, ValidationError
from codex_vm.store import JobStore
from tests.helpers import FakeRuntime, job_spec


class JobManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.runtime = FakeRuntime()
        self.manager = JobManager(JobStore(Path(self.temporary.name)), self.runtime, 1024)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    # LAB-REQ-JOB-001 and LAB-REQ-JOB-003: complete lifecycle and result evidence.
    def test_runs_complete_job(self) -> None:
        spec = JobSpec.from_dict(job_spec())
        self.manager.create(spec)
        self.manager.upload(spec.job_id, "source", BytesIO(b"source"), 6)
        self.manager.start(spec.job_id)
        for _ in range(100):
            state = self.manager.status(spec.job_id)
            if state["state"] == "succeeded":
                break
            time.sleep(0.01)
        self.assertEqual(state["state"], "succeeded")
        self.assertTrue(self.runtime.prepared)
        self.assertTrue(self.runtime.ran)
        names = {artifact["name"] for artifact in state["artifacts"]}
        self.assertEqual(names, {"release.zip", "stdout.log", "stderr.log"})
        artifact = self.manager.artifact_path(spec.job_id, "release.zip")
        self.assertEqual(artifact.read_bytes(), b"release")

    def test_does_not_start_before_all_inputs_arrive(self) -> None:
        spec = JobSpec.from_dict(job_spec())
        self.manager.create(spec)
        with self.assertRaisesRegex(ValidationError, "incomplete"):
            self.manager.start(spec.job_id)

    def test_allows_only_one_active_job(self) -> None:
        self.manager.create(JobSpec.from_dict(job_spec(job_id="first")))
        with self.assertRaisesRegex(RuntimeError, "active job"):
            self.manager.create(JobSpec.from_dict(job_spec(job_id="second")))

    def test_rejects_aggregate_input_over_worker_limit(self) -> None:
        value = job_spec(value=b"a" * 600)
        inputs = value["inputs"]
        assert isinstance(inputs, list)
        inputs.append(
            {
                "name": "package",
                "kind": "release-package",
                "size": 600,
                "sha256": f"sha256:{'b' * 64}",
            }
        )
        with self.assertRaisesRegex(ValidationError, "aggregate job input"):
            self.manager.create(JobSpec.from_dict(value))

    def test_rejects_unsafe_artifact_filename(self) -> None:
        spec = JobSpec.from_dict(job_spec())
        self.manager.create(spec)
        (self.manager.store.output_dir(spec.job_id) / "bad\r\nheader").write_bytes(b"bad")
        with self.assertRaisesRegex(ValidationError, "artifact name"):
            self.manager._collect_artifacts(spec.job_id)

    def test_rejects_aggregate_output_over_worker_limit(self) -> None:
        manager = JobManager(
            JobStore(Path(self.temporary.name) / "small-output"),
            self.runtime,
            1024,
            maximum_output_bytes=4,
        )
        spec = JobSpec.from_dict(job_spec(job_id="small-output"))
        manager.create(spec)
        manager.upload(spec.job_id, "source", BytesIO(b"source"), 6)
        manager.start(spec.job_id)
        for _ in range(100):
            state = manager.status(spec.job_id)
            if state["state"] == "failed":
                break
            time.sleep(0.01)
        self.assertEqual(state["state"], "failed")
        self.assertIn("aggregate job output", state["error"])


if __name__ == "__main__":
    unittest.main()
