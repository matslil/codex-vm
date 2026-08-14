"""Forge-independent local controller client and Git source exporter."""

from __future__ import annotations

import json
import shutil
import ssl
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .models import JobState
from .security import receive_verified, safe_name, sha256_file


class WorkerClient:
    def __init__(
        self,
        base_url: str,
        *,
        ca: Path | None = None,
        certificate: Path | None = None,
        private_key: Path | None = None,
        bearer_token: bytes | None = None,
        maximum_metadata_bytes: int = 1024 * 1024,
        maximum_artifact_bytes: int = 4 * 1024 * 1024 * 1024,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.maximum_metadata_bytes = maximum_metadata_bytes
        self.maximum_artifact_bytes = maximum_artifact_bytes
        parsed_url = urlsplit(self.base_url)
        if parsed_url.scheme not in {"http", "https"}:
            raise ValueError("worker URL must use HTTP or HTTPS")
        if parsed_url.scheme == "http" and parsed_url.hostname not in {
            "127.0.0.1",
            "::1",
            "localhost",
        }:
            raise ValueError("plain HTTP worker URLs must use a loopback host")
        self.bearer_token = bearer_token
        self.context = ssl.create_default_context(cafile=str(ca) if ca else None)
        if certificate is not None:
            self.context.load_cert_chain(certificate, private_key)

    def health(self) -> dict[str, Any]:
        return self._json("GET", "/v1/health")

    def submit(self, spec: dict[str, Any], input_paths: dict[str, Path]) -> dict[str, Any]:
        self._json("POST", "/v1/jobs", spec)
        job_id = str(spec["job_id"])
        for input_spec in spec.get("inputs", []):
            name = str(input_spec["name"])
            path = input_paths[name]
            self._bytes("PUT", f"/v1/jobs/{job_id}/inputs/{name}", path.read_bytes())
        return self._json("POST", f"/v1/jobs/{job_id}/start", {})

    def wait(self, job_id: str, poll_seconds: float = 1.0) -> dict[str, Any]:
        while True:
            state = self._json("GET", f"/v1/jobs/{job_id}")
            if JobState(state["state"]).terminal:
                return state
            time.sleep(poll_seconds)

    def download(self, job_id: str, artifact: dict[str, Any], destination: Path) -> None:
        safe_name(str(artifact["name"]))
        safe_name(str(artifact["filename"]))
        expected_url = f"/v1/jobs/{job_id}/artifacts/{artifact['name']}"
        if artifact["url"] != expected_url:
            raise ValueError(f"artifact URL is outside the expected job route: {artifact['name']}")
        request = Request(f"{self.base_url}{expected_url}", method="GET", headers=self._headers())
        try:
            with urlopen(request, context=self.context, timeout=60) as response:  # noqa: S310
                receive_verified(
                    response,
                    destination,
                    expected_size=int(artifact["size"]),
                    expected_digest=str(artifact["sha256"]),
                    maximum_size=self.maximum_artifact_bytes,
                )
        except HTTPError as error:
            try:
                detail = error.read(self.maximum_metadata_bytes).decode(errors="replace")
            finally:
                error.close()
            raise RuntimeError(f"worker returned HTTP {error.code}: {detail}") from error

    def _json(self, method: str, path: str, value: object | None = None) -> dict[str, Any]:
        body = None if value is None else json.dumps(value).encode()
        result = self._bytes(method, path, body, content_type="application/json")
        decoded = json.loads(result)
        if not isinstance(decoded, dict):
            raise RuntimeError("worker returned a non-object response")
        return dict(decoded)

    def _bytes(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        *,
        content_type: str = "application/octet-stream",
    ) -> bytes:
        headers = self._headers()
        headers["Content-Type"] = content_type
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers=headers,
        )
        try:
            with urlopen(request, context=self.context, timeout=60) as response:  # noqa: S310
                declared = response.headers.get("Content-Length")
                if declared is not None and int(declared) > self.maximum_metadata_bytes:
                    raise RuntimeError("worker metadata response is too large")
                result: bytes = response.read(self.maximum_metadata_bytes + 1)
                if len(result) > self.maximum_metadata_bytes:
                    raise RuntimeError("worker metadata response is too large")
                return result
        except HTTPError as error:
            try:
                detail = error.read(self.maximum_metadata_bytes).decode(errors="replace")
            finally:
                error.close()
            raise RuntimeError(f"worker returned HTTP {error.code}: {detail}") from error

    def _headers(self) -> dict[str, str]:
        if self.bearer_token is None:
            return {}
        return {"Authorization": f"Bearer {self.bearer_token.decode('ascii')}"}


def git_archive(
    repository: Path, revision: str, output: Path, prefix: str = "source/"
) -> dict[str, Any]:
    """Export one committed Git tree without granting the worker forge access."""
    repository = repository.resolve()
    commit = subprocess.run(
        ["git", "rev-parse", f"{revision}^{{commit}}"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tree = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{tree}}"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        temporary_output = Path(temporary) / output.name
        subprocess.run(
            [
                "git",
                "archive",
                "--format=tar.gz",
                f"--prefix={prefix}",
                f"--output={temporary_output}",
                commit,
            ],
            cwd=repository,
            check=True,
        )
        shutil.move(temporary_output, output)
    return {
        "kind": "git-archive",
        "commit": commit,
        "tree": tree,
        "filename": output.name,
        "size": output.stat().st_size,
        "sha256": sha256_file(output),
    }
