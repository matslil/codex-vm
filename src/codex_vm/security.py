"""Validation helpers for all data crossing the VM security boundary."""

from __future__ import annotations

import hashlib
import os
import secrets
import stat
import tempfile
from pathlib import Path
from typing import BinaryIO

from .models import NAME_RE, ValidationError


def create_bearer_token(path: Path) -> None:
    """Create a new token atomically without ever printing it or overwriting a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(secrets.token_urlsafe(32).encode("ascii") + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def load_bearer_token(path: Path) -> bytes:
    """Load a high-entropy token without accepting loose Unix permissions."""
    try:
        metadata = path.stat()
        value = path.read_bytes().strip()
    except OSError as error:
        raise ValueError(f"cannot read bearer token file: {path}") from error
    if os.name != "nt" and stat.S_IMODE(metadata.st_mode) & 0o077:
        raise ValueError("bearer token file must not be accessible by group or others")
    if not 32 <= len(value) <= 4096 or any(byte <= 0x20 or byte >= 0x7F for byte in value):
        raise ValueError("bearer token must contain 32 to 4096 printable ASCII characters")
    return value


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
