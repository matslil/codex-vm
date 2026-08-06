from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from codex_vm.models import JobSpec
from codex_vm.runtime import DockerRuntime
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
            runtime = DockerRuntime(windows_containers=False)
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

    @patch("codex_vm.runtime.subprocess.run")
    @patch("codex_vm.runtime.subprocess.Popen", return_value=ImmediateProcess())
    def test_windows_network_uses_nat_and_administrator(self, popen: Mock, run: Mock) -> None:
        value = job_spec()
        value["network"] = True
        spec = JobSpec.from_dict(value)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("input", "workspace", "scratch", "output"):
                (root / name).mkdir()
            DockerRuntime(windows_containers=True).run(spec, root, root / "stdout", root / "stderr")
        command = popen.call_args.args[0]
        self.assertNotIn("--privileged", command)
        self.assertIn("ContainerAdministrator", command)
        self.assertEqual(
            run.call_args_list[0].args[0],
            ["docker", "network", "create", "--driver", "nat", "codex-vm-job-1"],
        )


if __name__ == "__main__":
    unittest.main()
