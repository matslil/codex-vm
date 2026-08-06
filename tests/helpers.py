from __future__ import annotations

import hashlib
from pathlib import Path


def digest(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def job_spec(value: bytes = b"source", job_id: str = "job-1") -> dict[str, object]:
    return {
        "job_id": job_id,
        "operation": "build",
        "environment": {
            "image": "registry.lab/topal/build-linux-x64",
            "digest": f"sha256:{'a' * 64}",
        },
        "inputs": [
            {
                "name": "source",
                "kind": "git-archive",
                "size": len(value),
                "sha256": digest(value),
            }
        ],
        "command": ["/environment/run", "build"],
        "timeout_seconds": 30,
        "resources": {"cpus": 1, "memory_mb": 128, "disk_mb": 128},
    }


class FakeRuntime:
    def __init__(self) -> None:
        self.prepared = False
        self.ran = False
        self.cancelled = False

    def prepare(self, spec: object) -> None:
        self.prepared = True

    def run(self, spec: object, job_root: Path, stdout: Path, stderr: Path):
        from codex_vm.runtime import RuntimeResult

        self.ran = True
        stdout.write_text("build output\n", encoding="utf-8")
        stderr.write_text("", encoding="utf-8")
        (job_root / "output" / "release.zip").write_bytes(b"release")
        return RuntimeResult(exit_code=0)

    def cancel(self, job_id: str) -> None:
        self.cancelled = True
