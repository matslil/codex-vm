from __future__ import annotations

import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from codex_vm.models import JobSpec

REPOSITORY = Path(__file__).resolve().parents[1]
SECTOR_SIZE = 2048


def write_bootable_uefi_iso(path: Path) -> None:
    image = bytearray(26 * SECTOR_SIZE)
    primary = memoryview(image)[16 * SECTOR_SIZE : 17 * SECTOR_SIZE]
    primary[0] = 1
    primary[1:6] = b"CD001"
    primary[6] = 1

    boot_record = memoryview(image)[17 * SECTOR_SIZE : 18 * SECTOR_SIZE]
    boot_record[0] = 0
    boot_record[1:6] = b"CD001"
    boot_record[6] = 1
    boot_record[7:30] = b"EL TORITO SPECIFICATION"
    boot_record[71:75] = (20).to_bytes(4, "little")

    terminator = memoryview(image)[18 * SECTOR_SIZE : 19 * SECTOR_SIZE]
    terminator[0] = 255
    terminator[1:6] = b"CD001"
    terminator[6] = 1

    catalog = memoryview(image)[20 * SECTOR_SIZE : 21 * SECTOR_SIZE]
    catalog[0] = 1
    catalog[30:32] = b"\x55\xaa"
    checksum = (-sum(struct.unpack("<16H", catalog[:32]))) & 0xFFFF
    catalog[28:30] = checksum.to_bytes(2, "little")
    catalog[64] = 0x91
    catalog[65] = 0xEF
    catalog[66:68] = (1).to_bytes(2, "little")
    catalog[96] = 0x88
    catalog[104:108] = (25).to_bytes(4, "little")
    image[25 * SECTOR_SIZE : 25 * SECTOR_SIZE + 6] = b"PROMPT"
    path.write_bytes(image)


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
        self.assertIn("--token-file $Secrets\\controller.token", script)
        self.assertNotIn("--private-key", script)
        self.assertIn('-RemoteAddress "10.0.2.2"', script)
        self.assertNotIn("docker", script.lower())
        self.assertNotIn("containerd", script.lower())

    def test_base_builder_keeps_activation_key_guest_only(self) -> None:
        builder = (REPOSITORY / "provisioning/windows/build-base.sh").read_text(encoding="utf-8")
        answer_file = (REPOSITORY / "provisioning/windows/Autounattend.xml.in").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("--product-key", builder)
        self.assertIn("<Key>/IMAGE/INDEX</Key>", answer_file)
        self.assertIn("@@WINDOWS_IMAGE_INDEX@@", answer_file)
        self.assertNotIn("/IMAGE/NAME", answer_file)
        self.assertIn("@@WINDOWS_SETUP_KEY@@", answer_file)
        self.assertIn("<WillShowUI>Never</WillShowUI>", answer_file)
        self.assertIn("windows_image_index=1", builder)
        self.assertIn("TX9XD-98N7V-6WMQ6-BX7FG-H8Q99", builder)
        self.assertIn("cannot activate Windows", builder)
        self.assertIn("inside the VM using a secure PowerShell prompt", builder)
        self.assertIn("--internet", builder)

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
            fake_seven_zip = tools / "7z"
            fake_seven_zip.write_text(
                "#!/bin/sh\n"
                'case "$*" in\n'
                "  *efisys_noprompt.bin) printf NOPRMT ;;\n"
                "  *efisys.bin) printf PROMPT ;;\n"
                "  *) exit 2 ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            fake_qemu_img.chmod(0o755)
            fake_iso_builder.chmod(0o755)
            fake_seven_zip.chmod(0o755)
            windows_iso = root / "windows.iso"
            python_runtime = root / "python.zip"
            ovmf_code = root / "OVMF_CODE.fd"
            ovmf_vars = root / "OVMF_VARS.fd"
            write_bootable_uefi_iso(windows_iso)
            for path in (python_runtime, ovmf_code, ovmf_vars):
                path.write_bytes(path.name.encode())
            output = root / "vm"
            environment = os.environ.copy()
            environment.update(
                {
                    "QEMU_IMG": str(fake_qemu_img),
                    "ISO_BUILDER": str(fake_iso_builder),
                    "SEVEN_ZIP": str(fake_seven_zip),
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
            derived_media = output / "windows-installer-noprompt.iso"
            self.assertTrue(derived_media.is_file())
            self.assertEqual(
                derived_media.read_bytes()[25 * SECTOR_SIZE : 25 * SECTOR_SIZE + 6],
                b"NOPRMT",
            )
            self.assertEqual(
                windows_iso.read_bytes()[25 * SECTOR_SIZE : 25 * SECTOR_SIZE + 6],
                b"PROMPT",
            )
            self.assertTrue((output / "build-user-password").is_file())
            configuration = (output / "vm.conf").read_text(encoding="utf-8")
            self.assertIn("VM_ACCEL=tcg", configuration)
            self.assertNotIn("product", configuration.lower())
            self.assertRegex(manifest["derived_installer_iso_sha256"], r"^sha256:[0-9a-f]{64}$")

    def test_base_builder_rejects_an_html_download_as_windows_media(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            invalid_media = root / "windows.iso"
            invalid_media.write_text("<!doctype html><title>Download Windows</title>")

            result = subprocess.run(
                [
                    sys.executable,
                    str(REPOSITORY / "provisioning/windows/validate-install-media.py"),
                    str(invalid_media),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 65)
            self.assertIn("invalid Windows installation media", result.stderr)

    def test_windows_media_validator_accepts_a_bootable_uefi_iso(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            media = Path(directory) / "windows.iso"
            write_bootable_uefi_iso(media)

            result = subprocess.run(
                [
                    sys.executable,
                    str(REPOSITORY / "provisioning/windows/validate-install-media.py"),
                    str(media),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_install_boot_manager_ejects_dvd_after_first_reset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            socket_path = Path(directory) / "qmp.sock"
            received: list[dict[str, object]] = []
            server_error: list[BaseException] = []
            ready = threading.Event()

            def serve() -> None:
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                        listener.bind(str(socket_path))
                        listener.listen(1)
                        ready.set()
                        connection, _ = listener.accept()
                        with connection, connection.makefile("rwb") as stream:
                            stream.write(b'{"QMP":{"version":{},"capabilities":[]}}\n')
                            stream.flush()
                            for command in ("qmp_capabilities", "cont"):
                                request = json.loads(stream.readline())
                                received.append(request)
                                self.assertEqual(request["execute"], command)
                                response = {"return": {}, "id": request["id"]}
                                stream.write(json.dumps(response).encode() + b"\n")
                                stream.flush()
                            stream.write(b'{"event":"RESET","data":{"reason":"guest-reset"}}\n')
                            stream.flush()
                            request = json.loads(stream.readline())
                            received.append(request)
                            response = {"return": {}, "id": request["id"]}
                            stream.write(json.dumps(response).encode() + b"\n")
                            stream.flush()
                except BaseException as error:
                    server_error.append(error)

            thread = threading.Thread(target=serve)
            thread.start()
            self.assertTrue(ready.wait(timeout=2))
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPOSITORY / "provisioning/windows/manage-install-boot.py"),
                    str(socket_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            thread.join(timeout=2)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(thread.is_alive())
            self.assertEqual(server_error, [])
            self.assertEqual(received[-1]["execute"], "blockdev-open-tray")
            self.assertEqual(
                received[-1]["arguments"],
                {"device": "cdrom1", "force": True},
            )

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
            fake_host_python = tools / "python3"
            fake_host_python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_qemu.chmod(0o755)
            fake_swtpm.chmod(0o755)
            fake_host_python.chmod(0o755)
            disk = root / "windows-home-base.qcow2"
            code = root / "OVMF_CODE.fd"
            variables = root / "OVMF_VARS.fd"
            installer = root / "windows.iso"
            payload = root / "provisioning.iso"
            for path in (disk, code, variables, installer, payload):
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
                    "HOST_PYTHON": str(fake_host_python),
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
                    "--cdrom",
                    str(payload),
                    "--boot-cdrom",
                    "--display",
                    "none",
                    "--worker-port",
                    "18443",
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
            self.assertIn("ide-hd,drive=osdisk,bus=sata.0,bootindex=2", command)
            self.assertIn(
                "ide-cd,id=windows-installer,drive=cdrom1,bus=sata.1,bootindex=1",
                command,
            )
            self.assertIn("ide-cd,drive=cdrom2,bus=sata.2,bootindex=3", command)
            self.assertIn("-qmp unix:", command)
            self.assertIn("-S", command)
            self.assertIn("-boot menu=on", command)
            self.assertNotIn("once=d", command)
            self.assertIn("user,id=net0,restrict=on", command)
            self.assertIn("hostfwd=tcp:127.0.0.1:18443-:8443", command)

    def test_vm_launcher_separates_internet_from_worker_forwarding(self) -> None:
        result = subprocess.run(
            [
                str(REPOSITORY / "provisioning/windows/run-vm.sh"),
                "--vm-dir",
                "/unused",
                "--internet",
                "--worker-port",
                "18443",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 64)
        self.assertIn("cannot be combined", result.stderr)

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
