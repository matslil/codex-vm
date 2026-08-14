from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from codex_vm.api import WorkerHTTPServer
from codex_vm.controller import WorkerClient
from codex_vm.manager import JobManager
from codex_vm.store import JobStore
from tests.helpers import FakeRuntime, job_spec


class APITests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.token = b"test-token-0123456789-abcdefghijkl"
        manager = JobManager(JobStore(Path(self.temporary.name)), FakeRuntime(), 1024)
        self.server = WorkerHTTPServer(("127.0.0.1", 0), manager, bearer_token=self.token)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary.cleanup()

    def request(
        self, method: str, path: str, body: bytes | None = None, *, authenticated: bool = True
    ) -> tuple[int, bytes]:
        headers = {"Authorization": f"Bearer {self.token.decode()}"} if authenticated else {}
        request = Request(self.url + path, data=body, method=method, headers=headers)
        try:
            with urlopen(request, timeout=2) as response:  # noqa: S310
                return response.status, response.read()
        except HTTPError as error:
            try:
                return error.code, error.read()
            finally:
                error.close()

    # LAB-REQ-API-001: control and artifact exchange use the versioned HTTP API.
    def test_health_and_job_lifecycle(self) -> None:
        status, body = self.request("GET", "/v1/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["protocol"], 1)

        spec = job_spec()
        status, _ = self.request("POST", "/v1/jobs", json.dumps(spec).encode())
        self.assertEqual(status, 201)
        status, _ = self.request("PUT", "/v1/jobs/job-1/inputs/source", b"source")
        self.assertEqual(status, 200)
        status, _ = self.request("POST", "/v1/jobs/job-1/start", b"{}")
        self.assertEqual(status, 202)
        for _ in range(100):
            _, body = self.request("GET", "/v1/jobs/job-1")
            state = json.loads(body)
            if state["state"] == "succeeded":
                break
            time.sleep(0.01)
        self.assertEqual(state["state"], "succeeded")
        status, body = self.request("GET", "/v1/jobs/job-1/artifacts/release.zip")
        self.assertEqual((status, body), (200, b"release"))

    def test_requires_the_ephemeral_bearer_token(self) -> None:
        status, body = self.request("GET", "/v1/health", authenticated=False)
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(body)["error"], "authentication required")

        request = Request(
            self.url + "/v1/health",
            method="GET",
            headers={"Authorization": "Bearer wrong-token"},
        )
        with self.assertRaises(HTTPError) as context:
            urlopen(request, timeout=2)  # noqa: S310
        try:
            self.assertEqual(context.exception.code, 401)
        finally:
            context.exception.close()

        client = WorkerClient(self.url, bearer_token=self.token)
        self.assertEqual(client.health()["status"], "ready")

    def test_sanitizes_unexpected_server_errors(self) -> None:
        self.server.manager.status = Mock(side_effect=OSError("/secret/internal/path"))
        with self.assertLogs(level="ERROR"):
            status, body = self.request("GET", "/v1/jobs/job-1")
        self.assertEqual(status, 500)
        self.assertEqual(json.loads(body)["error"], "internal server error")
        self.assertNotIn(b"secret", body)

    def test_response_disables_caching_and_version_disclosure(self) -> None:
        request = Request(
            self.url + "/v1/health",
            headers={"Authorization": f"Bearer {self.token.decode()}"},
        )
        with urlopen(request, timeout=2) as response:  # noqa: S310
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
            self.assertEqual(response.headers["Connection"], "close")
            self.assertEqual(response.headers["Server"], "codex-vm")

    def test_rejects_unknown_input(self) -> None:
        self.request("POST", "/v1/jobs", json.dumps(job_spec()).encode())
        status, body = self.request("PUT", "/v1/jobs/job-1/inputs/other", b"source")
        self.assertEqual(status, 404)
        self.assertIn("other", json.loads(body)["error"])


if __name__ == "__main__":
    unittest.main()
