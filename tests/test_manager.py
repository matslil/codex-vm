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


if __name__ == "__main__":
    unittest.main()
