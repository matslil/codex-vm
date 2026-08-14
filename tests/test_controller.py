from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from codex_vm.controller import WorkerClient, git_archive
from codex_vm.models import ValidationError
from codex_vm.security import sha256_file


class GitArchiveTests(unittest.TestCase):
    # LAB-REQ-SRC-001 and LAB-REQ-SRC-002.
    def test_exports_exact_committed_tree_with_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repository"
            repository.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.invalid"],
                cwd=repository,
                check=True,
            )
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repository, check=True)
            (repository / "tracked.txt").write_text("tracked\n", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.txt"], cwd=repository, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=repository, check=True)
            (repository / "untracked.txt").write_text("untracked\n", encoding="utf-8")
            output = Path(directory) / "source.tar.gz"
            manifest = git_archive(repository, "HEAD", output)
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repository,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            self.assertEqual(manifest["commit"], commit)
            self.assertEqual(manifest["size"], output.stat().st_size)
            self.assertEqual(manifest["sha256"], sha256_file(output))


class WorkerClientArtifactTests(unittest.TestCase):
    def test_rejects_plain_http_outside_loopback(self) -> None:
        with self.assertRaisesRegex(ValueError, "loopback"):
            WorkerClient("http://worker.invalid", bearer_token=b"a" * 43)

    def test_rejects_artifact_path_outside_expected_job_route(self) -> None:
        client = WorkerClient("https://worker.invalid")
        artifact = {
            "name": "release.zip",
            "filename": "release.zip",
            "size": 1,
            "sha256": f"sha256:{'a' * 64}",
            "url": "https://attacker.invalid/release.zip",
        }
        with (
            tempfile.TemporaryDirectory() as directory,
            self.assertRaisesRegex(ValueError, "outside"),
        ):
            client.download("job-1", artifact, Path(directory) / "release.zip")

    def test_rejects_artifact_path_traversal(self) -> None:
        client = WorkerClient("https://worker.invalid")
        artifact = {
            "name": "../release.zip",
            "filename": "release.zip",
            "size": 1,
            "sha256": f"sha256:{'a' * 64}",
            "url": "/v1/jobs/job-1/artifacts/release.zip",
        }
        with (
            tempfile.TemporaryDirectory() as directory,
            self.assertRaisesRegex(ValidationError, "name"),
        ):
            client.download("job-1", artifact, Path(directory) / "release.zip")


if __name__ == "__main__":
    unittest.main()
