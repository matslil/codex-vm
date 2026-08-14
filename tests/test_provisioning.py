from __future__ import annotations

import json
import os
import subprocess
import sys
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
        self.assertIn("[switch]$PortablePython", script)
        self.assertNotIn("docker", script.lower())
        self.assertNotIn("containerd", script.lower())

    def test_base_builder_never_accepts_a_product_key(self) -> None:
        builder = (REPOSITORY / "provisioning/windows/build-base.sh").read_text(encoding="utf-8")
        answer_file = (REPOSITORY / "provisioning/windows/Autounattend.xml.in").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("--product-key", builder)
        self.assertNotIn("ProductKey", answer_file)
        self.assertIn("inside the VM using a secure PowerShell prompt", builder)

    def test_base_builder_prepares_artifacts_without_a_vm(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tools = root / "tools"
            tools.mkdir()
            fake_qemu_img = tools / "qemu-img"
            fake_qemu_img.write_text(
                "#!/bin/sh\n"
                'for argument do previous="$output"; output="$argument"; done\n'
                ': > "$previous"\n',
                encoding="utf-8",
            )
            fake_iso_builder = tools / "genisoimage"
            fake_iso_builder.write_text(
                "#!/bin/sh\n"
                'while [ "$#" -gt 0 ]; do\n'
                '  if [ "$1" = -o ]; then shift; output=$1; fi\n'
                "  shift\n"
                "done\n"
                ': > "$output"\n',
                encoding="utf-8",
            )
            fake_qemu_img.chmod(0o755)
            fake_iso_builder.chmod(0o755)
            windows_iso = root / "windows.iso"
            python_runtime = root / "python.zip"
            ovmf_code = root / "OVMF_CODE.fd"
            ovmf_vars = root / "OVMF_VARS.fd"
            for path in (windows_iso, python_runtime, ovmf_code, ovmf_vars):
                path.write_bytes(path.name.encode())
            output = root / "vm"
            environment = os.environ.copy()
            environment.update(
                {
                    "QEMU_IMG": str(fake_qemu_img),
                    "ISO_BUILDER": str(fake_iso_builder),
                    "HOST_PYTHON": sys.executable,
                }
            )

            result = subprocess.run(
                [
                    str(REPOSITORY / "provisioning/windows/build-base.sh"),
                    "--iso",
                    str(windows_iso),
                    "--python-source",
                    str(python_runtime),
                    "--ovmf-code",
                    str(ovmf_code),
                    "--ovmf-vars",
                    str(ovmf_vars),
                    "--output",
                    str(output),
                    "--disk-size",
                    "1G",
                    "--memory-mb",
                    "4096",
                    "--cpus",
                    "2",
                    "--accel",
                    "tcg",
                    "--prepare-only",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "prepared")
            self.assertEqual(manifest["edition"], "Windows 11 Home")
            self.assertTrue((output / "windows-home-base.qcow2").is_file())
            self.assertTrue((output / "provisioning.iso").is_file())
            self.assertTrue((output / "build-user-password").is_file())
            configuration = (output / "vm.conf").read_text(encoding="utf-8")
            self.assertIn("VM_ACCEL=tcg", configuration)
            self.assertNotIn("product", configuration.lower())

    def test_vm_launcher_uses_stable_identity_and_tpm(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tools = root / "tools"
            tools.mkdir()
            qemu_log = root / "qemu.log"
            fake_qemu = tools / "qemu-system-x86_64"
            fake_qemu.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$*" > "$QEMU_LOG"\n',
                encoding="utf-8",
            )
            fake_swtpm = tools / "swtpm"
            fake_swtpm.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_qemu.chmod(0o755)
            fake_swtpm.chmod(0o755)
            disk = root / "windows-home-base.qcow2"
            code = root / "OVMF_CODE.fd"
            variables = root / "OVMF_VARS.fd"
            installer = root / "windows.iso"
            for path in (disk, code, variables, installer):
                path.write_bytes(path.name.encode())
            (root / "vm.conf").write_text(
                "VM_UUID=11111111-2222-3333-4444-555555555555\n"
                "VM_MAC=52:54:00:12:34:56\n"
                "VM_MEMORY_MB=4096\n"
                "VM_CPUS=2\n"
                "VM_ACCEL=tcg\n"
                "VM_CPU_MODEL=max\n"
                f"VM_OVMF_CODE={code}\n"
                f"VM_OVMF_VARS={variables}\n",
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment.update(
                {
                    "QEMU_SYSTEM_X86_64": str(fake_qemu),
                    "SWTPM": str(fake_swtpm),
                    "QEMU_LOG": str(qemu_log),
                }
            )

            result = subprocess.run(
                [
                    str(REPOSITORY / "provisioning/windows/run-vm.sh"),
                    "--vm-dir",
                    str(root),
                    "--cdrom",
                    str(installer),
                    "--boot-cdrom",
                    "--display",
                    "none",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            command = qemu_log.read_text(encoding="utf-8")
            self.assertIn("-uuid 11111111-2222-3333-4444-555555555555", command)
            self.assertIn("e1000e,netdev=net0,mac=52:54:00:12:34:56", command)
            self.assertIn("-device tpm-crb,tpmdev=tpm0", command)
            self.assertIn("property=secure,value=on", command)
            self.assertIn("-boot menu=on,once=d", command)

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
