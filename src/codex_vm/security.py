"""Validation helpers for all data crossing the VM security boundary."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import BinaryIO

from .models import NAME_RE, ValidationError


def safe_name(value: str) -> str:
    if not NAME_RE.fullmatch(value):
        raise ValidationError("artifact name is invalid")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


def receive_verified(
    source: BinaryIO,
    destination: Path,
    *,
    expected_size: int,
    expected_digest: str,
    maximum_size: int,
) -> None:
    """Write an input atomically while enforcing its declared limits and digest."""
    if expected_size > maximum_size:
        raise ValidationError("input exceeds worker size limit")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".upload-", dir=destination.parent)
    digest = hashlib.sha256()
    received = 0
    try:
        with os.fdopen(descriptor, "wb") as output:
            while received < expected_size:
                block = source.read(min(1024 * 1024, expected_size - received))
                if not block:
                    break
                received += len(block)
                if received > maximum_size:
                    raise ValidationError("input exceeds worker size limit")
                digest.update(block)
                output.write(block)
            output.flush()
            os.fsync(output.fileno())
        actual_digest = f"sha256:{digest.hexdigest()}"
        if received != expected_size:
            message = f"input length mismatch: expected {expected_size}, received {received}"
            raise ValidationError(message)
        if actual_digest != expected_digest:
            raise ValidationError("input digest mismatch")
        os.replace(temporary_name, destination)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise
