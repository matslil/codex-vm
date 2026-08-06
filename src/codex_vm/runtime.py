"""Container runtime boundary used by the VM worker."""

from __future__ import annotations

import os
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .models import JobSpec


@dataclass(frozen=True)
class RuntimeResult:
    exit_code: int
    timed_out: bool = False
    cancelled: bool = False


class ContainerRuntime(Protocol):
    def prepare(self, spec: JobSpec) -> None: ...

    def run(self, spec: JobSpec, job_root: Path, stdout: Path, stderr: Path) -> RuntimeResult: ...

    def cancel(self, job_id: str) -> None: ...


class DockerRuntime:
    """Run one digest-pinned environment container for a job.

    Linux containers are deliberately privileged. Windows containers run as
    ContainerAdministrator because Docker's Linux --privileged switch has no
    direct Windows equivalent. The disposable VM is the security boundary.
    """

    def __init__(self, executable: str = "docker", windows_containers: bool | None = None) -> None:
        self.executable = executable
        self.windows_containers = (
            os.name == "nt" if windows_containers is None else windows_containers
        )
        self._processes: dict[str, subprocess.Popen[bytes]] = {}
        self._cancelled: set[str] = set()
        self._lock = threading.Lock()

    def prepare(self, spec: JobSpec) -> None:
        subprocess.run(
            [self.executable, "pull", spec.environment.pinned_image],
            check=True,
            stdin=subprocess.DEVNULL,
        )

    def run(self, spec: JobSpec, job_root: Path, stdout: Path, stderr: Path) -> RuntimeResult:
        name = f"codex-vm-{spec.job_id}"
        network = f"codex-vm-{spec.job_id}"
        if spec.network:
            network_command = [self.executable, "network", "create"]
            if self.windows_containers:
                network_command.extend(["--driver", "nat"])
            network_command.append(network)
            subprocess.run(network_command, check=True, stdin=subprocess.DEVNULL)
        command = [
            self.executable,
            "run",
            "--rm",
            "--name",
            name,
            "--cpus",
            str(spec.resources.cpus),
            "--memory",
            f"{spec.resources.memory_mb}m",
        ]
        if self.windows_containers:
            command.extend(["--user", "ContainerAdministrator"])
            mounts = {
                "input": "C:\\job\\input",
                "workspace": "C:\\job\\workspace",
                "scratch": "C:\\job\\scratch",
                "output": "C:\\job\\output",
            }
        else:
            command.append("--privileged")
            mounts = {
                "input": "/job/input",
                "workspace": "/job/workspace",
                "scratch": "/job/scratch",
                "output": "/job/output",
            }
        if spec.network:
            command.extend(["--network", network])
        else:
            command.extend(["--network", "none"])
        for local_name, container_path in mounts.items():
            mode = ",readonly" if local_name == "input" else ""
            command.extend(
                [
                    "--mount",
                    f"type=bind,src={job_root / local_name},dst={container_path}{mode}",
                ]
            )
        command.append(spec.environment.pinned_image)
        command.extend(spec.command)

        try:
            with stdout.open("wb") as stdout_stream, stderr.open("wb") as stderr_stream:
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_stream,
                    stderr=stderr_stream,
                )
                with self._lock:
                    self._processes[spec.job_id] = process
                try:
                    exit_code = process.wait(timeout=spec.timeout_seconds)
                    with self._lock:
                        cancelled = spec.job_id in self._cancelled
                    return RuntimeResult(exit_code=exit_code, cancelled=cancelled)
                except subprocess.TimeoutExpired:
                    self._stop(name)
                    process.wait(timeout=30)
                    return RuntimeResult(exit_code=124, timed_out=True)
                finally:
                    with self._lock:
                        self._processes.pop(spec.job_id, None)
                        self._cancelled.discard(spec.job_id)
        finally:
            if spec.network:
                subprocess.run(
                    [self.executable, "network", "rm", network],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

    def cancel(self, job_id: str) -> None:
        with self._lock:
            process = self._processes.get(job_id)
            if process is None:
                return
            self._cancelled.add(job_id)
        self._stop(f"codex-vm-{job_id}")

    def _stop(self, name: str) -> None:
        subprocess.run(
            [self.executable, "stop", "--time", "10", name],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
