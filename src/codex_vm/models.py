"""Versioned messages exchanged between a controller and a disposable worker."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class ValidationError(ValueError):
    """A message does not meet the public protocol contract."""


class JobState(StrEnum):
    CREATED = "created"
    RECEIVING_INPUT = "receiving-input"
    PREPARING_ENVIRONMENT = "preparing-environment"
    READY = "ready"
    RUNNING = "running"
    COLLECTING_RESULTS = "collecting-results"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed-out"

    @property
    def terminal(self) -> bool:
        return self in {
            JobState.SUCCEEDED,
            JobState.FAILED,
            JobState.CANCELLED,
            JobState.TIMED_OUT,
        }


@dataclass(frozen=True)
class InputSpec:
    name: str
    kind: str
    sha256: str
    size: int

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> InputSpec:
        result = cls(
            name=str(value.get("name", "")),
            kind=str(value.get("kind", "")),
            sha256=str(value.get("sha256", "")),
            size=int(value.get("size", -1)),
        )
        if not NAME_RE.fullmatch(result.name):
            raise ValidationError("input name is invalid")
        if not result.kind or len(result.kind) > 128:
            raise ValidationError("input kind is invalid")
        if not SHA256_RE.fullmatch(result.sha256):
            raise ValidationError("input sha256 must be a lowercase sha256 digest")
        if result.size < 0:
            raise ValidationError("input size cannot be negative")
        return result


@dataclass(frozen=True)
class EnvironmentSpec:
    image: str
    digest: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> EnvironmentSpec:
        result = cls(image=str(value.get("image", "")), digest=str(value.get("digest", "")))
        if not result.image or any(char.isspace() for char in result.image):
            raise ValidationError("environment image is invalid")
        if "@" in result.image:
            raise ValidationError("environment image and digest must be separate fields")
        if not SHA256_RE.fullmatch(result.digest):
            raise ValidationError("environment digest must be a lowercase sha256 digest")
        return result

    @property
    def pinned_image(self) -> str:
        return f"{self.image}@{self.digest}"


@dataclass(frozen=True)
class ResourceSpec:
    cpus: float = 2.0
    memory_mb: int = 4096
    disk_mb: int = 4096

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ResourceSpec:
        result = cls(
            cpus=float(value.get("cpus", 2.0)),
            memory_mb=int(value.get("memory_mb", 4096)),
            disk_mb=int(value.get("disk_mb", 4096)),
        )
        if not 0.1 <= result.cpus <= 256:
            raise ValidationError("cpus must be between 0.1 and 256")
        if not 64 <= result.memory_mb <= 1_048_576:
            raise ValidationError("memory_mb must be between 64 and 1048576")
        if not 16 <= result.disk_mb <= 10_485_760:
            raise ValidationError("disk_mb must be between 16 and 10485760")
        return result


@dataclass(frozen=True)
class JobSpec:
    job_id: str
    operation: str
    environment: EnvironmentSpec
    inputs: tuple[InputSpec, ...]
    command: tuple[str, ...]
    timeout_seconds: int = 3600
    resources: ResourceSpec = field(default_factory=ResourceSpec)
    network: bool = False

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> JobSpec:
        raw_command = value.get("command", [])
        if not isinstance(raw_command, list) or not all(
            isinstance(item, str) for item in raw_command
        ):
            raise ValidationError("command must be an array of strings")
        raw_inputs = value.get("inputs", [])
        if not isinstance(raw_inputs, list):
            raise ValidationError("inputs must be an array")
        raw_environment = value.get("environment")
        if not isinstance(raw_environment, dict):
            raise ValidationError("environment must be an object")
        raw_resources = value.get("resources", {})
        if not isinstance(raw_resources, dict):
            raise ValidationError("resources must be an object")
        result = cls(
            job_id=str(value.get("job_id", "")),
            operation=str(value.get("operation", "")),
            environment=EnvironmentSpec.from_dict(raw_environment),
            inputs=tuple(InputSpec.from_dict(item) for item in raw_inputs),
            command=tuple(raw_command),
            timeout_seconds=int(value.get("timeout_seconds", 3600)),
            resources=ResourceSpec.from_dict(raw_resources),
            network=bool(value.get("network", False)),
        )
        if not JOB_ID_RE.fullmatch(result.job_id):
            raise ValidationError("job_id is invalid")
        if not result.operation or len(result.operation) > 128:
            raise ValidationError("operation is invalid")
        if not result.command or not result.command[0]:
            raise ValidationError("command cannot be empty")
        if not 1 <= result.timeout_seconds <= 86_400:
            raise ValidationError("timeout_seconds must be between 1 and 86400")
        if len({item.name for item in result.inputs}) != len(result.inputs):
            raise ValidationError("input names must be unique")
        return result

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Artifact:
    name: str
    kind: str
    filename: str
    size: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
