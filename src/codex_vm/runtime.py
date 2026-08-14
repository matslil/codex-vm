"""Platform runtime boundary used by the VM worker."""

from __future__ import annotations

import json
import os
import stat
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


class EnvironmentRuntime(Protocol):
    def prepare(self, spec: JobSpec) -> None: ...

    def run(self, spec: JobSpec, job_root: Path, stdout: Path, stderr: Path) -> RuntimeResult: ...

    def cancel(self, job_id: str) -> None: ...


class DockerRuntime:
    """Run one digest-pinned privileged Linux environment container."""

    def __init__(self, executable: str = "docker") -> None:
        self.executable = executable
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
            subprocess.run(
                [self.executable, "network", "create", network],
                check=True,
                stdin=subprocess.DEVNULL,
            )
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


class NativeRuntime:
    """Run a job in the environment baked into a disposable VM layer.

    The manifest prevents a controller from accidentally sending a job to a
    differently provisioned VM. Resource and network isolation are owned by
    the outer VM provider for this runtime.
    """

    def __init__(self, manifest: Path) -> None:
        self.manifest = manifest
        self._processes: dict[str, subprocess.Popen[bytes]] = {}
        self._cancelled: set[str] = set()
        self._lock = threading.Lock()

    def prepare(self, spec: JobSpec) -> None:
        try:
            value = json.loads(self.manifest.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"cannot read native environment manifest: {error}") from error
        if value.get("schema") != 1:
            raise RuntimeError("unsupported native environment manifest schema")
        if value.get("reference") != spec.environment.reference:
            raise RuntimeError("native environment reference does not match job")
        if value.get("digest") != spec.environment.digest:
            raise RuntimeError("native environment digest does not match job")

    def run(self, spec: JobSpec, job_root: Path, stdout: Path, stderr: Path) -> RuntimeResult:
        environment = os.environ.copy()
        for name in ("input", "workspace", "scratch", "output"):
            environment[f"CODEX_VM_{name.upper()}"] = str((job_root / name).resolve())
        environment["CODEX_VM_JOB_ID"] = spec.job_id
        environment["CODEX_VM_OPERATION"] = spec.operation
        for path in (job_root / "input").iterdir():
            if path.is_file() and not path.is_symlink():
                path.chmod(stat.S_IREAD)

        with stdout.open("wb") as stdout_stream, stderr.open("wb") as stderr_stream:
            process = subprocess.Popen(
                list(spec.command),
                cwd=job_root / "workspace",
                env=environment,
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
                self._stop(process)
                process.wait(timeout=30)
                return RuntimeResult(exit_code=124, timed_out=True)
            finally:
                with self._lock:
                    self._processes.pop(spec.job_id, None)
                    self._cancelled.discard(spec.job_id)

    def cancel(self, job_id: str) -> None:
        with self._lock:
            process = self._processes.get(job_id)
            if process is None:
                return
            self._cancelled.add(job_id)
        self._stop(process)

    @staticmethod
    def _stop(process: subprocess.Popen[bytes]) -> None:
        if os.name == "nt":
            subprocess.run(
                ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            process.terminate()
