from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from codex_vm.models import JobSpec
from codex_vm.runtime import DockerRuntime, NativeRuntime
from tests.helpers import job_spec


class ImmediateProcess:
    def wait(self, timeout: int) -> int:
        return 0


class DockerRuntimeTests(unittest.TestCase):
    # LAB-REQ-JOB-002, LAB-REQ-IO-001, LAB-REQ-NET-001.
    @patch("codex_vm.runtime.subprocess.Popen", return_value=ImmediateProcess())
    def test_linux_command_is_pinned_privileged_and_offline(self, popen: Mock) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("input", "workspace", "scratch", "output"):
                (root / name).mkdir()
            runtime = DockerRuntime()
            spec = JobSpec.from_dict(job_spec())
            result = runtime.run(spec, root, root / "stdout", root / "stderr")
        command = popen.call_args.args[0]
        self.assertEqual(result.exit_code, 0)
        self.assertIn("--privileged", command)
        self.assertIn("none", command)
        self.assertIn(spec.environment.pinned_image, command)
        input_mount = next(item for item in command if "dst=/job/input" in item)
        self.assertTrue(input_mount.endswith(",readonly"))

    @patch("codex_vm.runtime.subprocess.run")
    def test_prepare_pulls_exact_digest(self, run: Mock) -> None:
        runtime = DockerRuntime()
        spec = JobSpec.from_dict(job_spec())
        runtime.prepare(spec)
        run.assert_called_once_with(
            ["docker", "pull", spec.environment.pinned_image],
            check=True,
            stdin=subprocess.DEVNULL,
        )


class NativeRuntimeTests(unittest.TestCase):
    # LAB-REQ-ENV-002: a native worker only accepts its baked environment.
    def test_prepare_verifies_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "environment.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "reference": "registry.lab/topal/build-linux-x64",
                        "digest": f"sha256:{'a' * 64}",
                    }
                ),
                encoding="utf-8",
            )
            NativeRuntime(manifest).prepare(JobSpec.from_dict(job_spec()))

    def test_prepare_rejects_wrong_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "environment.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "reference": "wrong/environment",
                        "digest": f"sha256:{'a' * 64}",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "reference"):
                NativeRuntime(manifest).prepare(JobSpec.from_dict(job_spec()))

    @patch("codex_vm.runtime.subprocess.Popen", return_value=ImmediateProcess())
    def test_run_exposes_native_job_paths(self, popen: Mock) -> None:
        spec = JobSpec.from_dict(job_spec())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("input", "workspace", "scratch", "output"):
                (root / name).mkdir()
            input_file = root / "input" / "release.zip"
            input_file.write_bytes(b"release")
            result = NativeRuntime(root / "environment.json").run(
                spec, root, root / "stdout", root / "stderr"
            )
            self.assertFalse(input_file.stat().st_mode & 0o222)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(popen.call_args.kwargs["cwd"], root / "workspace")
        environment = popen.call_args.kwargs["env"]
        self.assertEqual(environment["CODEX_VM_JOB_ID"], "job-1")
        self.assertEqual(environment["CODEX_VM_OUTPUT"], str((root / "output").resolve()))


if __name__ == "__main__":
    unittest.main()
