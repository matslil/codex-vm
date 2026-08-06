"""Small HTTPS REST API exposed by a disposable worker VM."""

from __future__ import annotations

import json
import ssl
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, BinaryIO, cast
from urllib.parse import unquote, urlsplit

from .manager import JobManager
from .models import JobSpec, ValidationError


class WorkerHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], manager: JobManager) -> None:
        super().__init__(address, WorkerRequestHandler)
        self.manager = manager


class WorkerRequestHandler(BaseHTTPRequestHandler):
    server: WorkerHTTPServer
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        parts = self._parts()
        try:
            if parts == ["v1", "health"]:
                self._json(HTTPStatus.OK, {"status": "ready", "protocol": 1})
            elif len(parts) == 3 and parts[:2] == ["v1", "jobs"]:
                self._json(HTTPStatus.OK, self.server.manager.status(parts[2]))
            elif len(parts) == 5 and parts[:2] == ["v1", "jobs"] and parts[3] == "artifacts":
                self._file(self.server.manager.artifact_path(parts[2], parts[4]))
            else:
                self._error(HTTPStatus.NOT_FOUND, "route not found")
        except Exception as error:
            self._handle(error)

    def do_POST(self) -> None:  # noqa: N802
        parts = self._parts()
        try:
            if parts == ["v1", "jobs"]:
                value = self._read_json()
                self._json(HTTPStatus.CREATED, self.server.manager.create(JobSpec.from_dict(value)))
            elif len(parts) == 4 and parts[:2] == ["v1", "jobs"] and parts[3] == "start":
                self._json(HTTPStatus.ACCEPTED, self.server.manager.start(parts[2]))
            elif len(parts) == 4 and parts[:2] == ["v1", "jobs"] and parts[3] == "cancel":
                self._json(HTTPStatus.ACCEPTED, self.server.manager.cancel(parts[2]))
            else:
                self._error(HTTPStatus.NOT_FOUND, "route not found")
        except Exception as error:
            self._handle(error)

    def do_PUT(self) -> None:  # noqa: N802
        parts = self._parts()
        try:
            if len(parts) != 5 or parts[:2] != ["v1", "jobs"] or parts[3] != "inputs":
                self._error(HTTPStatus.NOT_FOUND, "route not found")
                return
            length = self._content_length()
            stream = cast(BinaryIO, self.rfile)
            state = self.server.manager.upload(parts[2], parts[4], stream, length)
            self._json(HTTPStatus.OK, state)
        except Exception as error:
            self._handle(error)

    def log_message(self, format_string: str, *args: object) -> None:
        # The service unit captures a compact access log without request bodies.
        super().log_message(format_string, *args)

    def _parts(self) -> list[str]:
        return [unquote(item) for item in urlsplit(self.path).path.split("/") if item]

    def _content_length(self) -> int:
        value = self.headers.get("Content-Length")
        if value is None:
            raise ValidationError("Content-Length is required")
        try:
            length = int(value)
        except ValueError as error:
            raise ValidationError("Content-Length is invalid") from error
        if length < 0:
            raise ValidationError("Content-Length is invalid")
        return length

    def _read_json(self) -> dict[str, Any]:
        length = self._content_length()
        if length > 1024 * 1024:
            raise ValidationError("JSON request is too large")
        try:
            value = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValidationError("request body is not valid JSON") from error
        if not isinstance(value, dict):
            raise ValidationError("request body must be a JSON object")
        return value

    def _json(self, status: HTTPStatus, value: object) -> None:
        body = json.dumps(value, sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path) -> None:
        size = path.stat().st_size
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
        self.end_headers()
        with path.open("rb") as stream:
            while block := stream.read(1024 * 1024):
                self.wfile.write(block)

    def _error(self, status: HTTPStatus, message: str) -> None:
        self._json(status, {"error": message})

    def _handle(self, error: Exception) -> None:
        if isinstance(error, FileNotFoundError):
            status = HTTPStatus.NOT_FOUND
        elif isinstance(error, (ValidationError, ValueError)):
            status = HTTPStatus.BAD_REQUEST
        elif isinstance(error, (FileExistsError, RuntimeError)):
            status = HTTPStatus.CONFLICT
        else:
            status = HTTPStatus.INTERNAL_SERVER_ERROR
        self._error(status, str(error) or type(error).__name__)


def serve(
    manager: JobManager,
    host: str,
    port: int,
    *,
    certificate: Path | None = None,
    private_key: Path | None = None,
    client_ca: Path | None = None,
) -> None:
    server = WorkerHTTPServer((host, port), manager)
    if any(item is not None for item in (certificate, private_key, client_ca)):
        if certificate is None or private_key is None or client_ca is None:
            raise ValueError("certificate, private key, and client CA are all required for TLS")
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_cert_chain(certificate, private_key)
        context.load_verify_locations(client_ca)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()
