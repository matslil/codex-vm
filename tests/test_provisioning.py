from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from codex_vm.models import JobSpec

REPOSITORY = Path(__file__).resolve().parents[1]


class WindowsProvisioningTests(unittest.TestCase):
    # LAB-REQ-OPS-003, LAB-VER-015: host-side inspection without a Windows VM.
    def test_worker_uses_secure_activation_and_native_sessions(self) -> None:
        script = (REPOSITORY / "provisioning/windows/install-worker.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn('Read-Host -AsSecureString "Windows product key"', script)
        self.assertIn("Invoke-CimMethod", script)
        self.assertNotIn("[string]$ProductKey", script)
        self.assertIn("serve --runtime native", script)
        self.assertIn('ValidateSet("System", "Interactive")', script)
        self.assertIn("New-ScheduledTaskTrigger -AtLogOn", script)
        self.assertNotIn("docker", script.lower())
        self.assertNotIn("containerd", script.lower())

    def test_windows_example_uses_common_job_schema(self) -> None:
        value = json.loads(
            (REPOSITORY / "config/job.windows.example.json").read_text(encoding="utf-8")
        )
        spec = JobSpec.from_dict(value)
        self.assertEqual(spec.environment.reference, value["environment"]["reference"])
        self.assertEqual(spec.command[0], "powershell.exe")

    def test_job_overlay_uses_read_only_qcow2_backing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tools = root / "tools"
            tools.mkdir()
            log = root / "qemu.log"
            fake_qemu = tools / "qemu-img"
            fake_qemu.write_text(
                "#!/bin/sh\n"
                'printf "%s\\n" "$*" >> "$QEMU_LOG"\n'
                'if [ "$1" = create ]; then\n'
                '  for argument do output="$argument"; done\n'
                '  : > "$output"\n'
                "fi\n",
                encoding="utf-8",
            )
            fake_qemu.chmod(0o755)
            parent = root / "environment.qcow2"
            parent.write_bytes(b"parent")
            output = root / "job.qcow2"
            environment = os.environ.copy()
            environment["PATH"] = f"{tools}{os.pathsep}{environment['PATH']}"
            environment["QEMU_LOG"] = str(log)

            result = subprocess.run(
                [
                    "sh",
                    str(REPOSITORY / "provisioning/windows/new-job-overlay.sh"),
                    str(parent),
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            commands = log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(
                commands[0],
                f"create -f qcow2 -F qcow2 -b {parent.resolve()} {output}",
            )
            self.assertEqual(commands[1], f"info --output=json {output}")

    def test_job_overlay_refuses_to_overwrite_a_disk(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = root / "environment.qcow2"
            output = root / "job.qcow2"
            parent.write_bytes(b"parent")
            output.write_bytes(b"keep")
            result = subprocess.run(
                [
                    "sh",
                    str(REPOSITORY / "provisioning/windows/new-job-overlay.sh"),
                    str(parent),
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 73)
            self.assertEqual(output.read_bytes(), b"keep")


if __name__ == "__main__":
    unittest.main()
