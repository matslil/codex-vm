from __future__ import annotations

import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from codex_vm.models import ValidationError
from codex_vm.security import (
    create_bearer_token,
    load_bearer_token,
    receive_verified,
    sha256_file,
)
from tests.helpers import digest


class ReceiveVerifiedTests(unittest.TestCase):
    # LAB-REQ-ART-002: input is accepted only after length and digest verification.
    def test_atomically_accepts_matching_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "input" / "source"
            receive_verified(
                BytesIO(b"hello"),
                destination,
                expected_size=5,
                expected_digest=digest(b"hello"),
                maximum_size=10,
            )
            self.assertEqual(destination.read_bytes(), b"hello")
            self.assertEqual(sha256_file(destination), digest(b"hello"))

    def test_removes_partial_file_on_digest_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "input"
            with self.assertRaisesRegex(ValidationError, "digest"):
                receive_verified(
                    BytesIO(b"hello"),
                    destination,
                    expected_size=5,
                    expected_digest=digest(b"other"),
                    maximum_size=10,
                )
            self.assertFalse(destination.exists())

    def test_rejects_oversize_declaration_without_reading(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            self.assertRaisesRegex(ValidationError, "size limit"),
        ):
            receive_verified(
                BytesIO(b"hello"),
                Path(directory) / "input",
                expected_size=5,
                expected_digest=digest(b"hello"),
                maximum_size=4,
            )


class BearerTokenTests(unittest.TestCase):
    def test_creates_private_token_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "job" / "controller.token"
            create_bearer_token(path)
            self.assertGreaterEqual(len(load_bearer_token(path)), 32)
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                create_bearer_token(path)

    def test_loads_private_high_entropy_token(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "controller.token"
            path.write_text("a" * 43 + "\n", encoding="ascii")
            path.chmod(0o600)
            self.assertEqual(load_bearer_token(path), b"a" * 43)

    @unittest.skipIf(os.name == "nt", "POSIX permission check")
    def test_rejects_public_token_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "controller.token"
            path.write_text("a" * 43, encoding="ascii")
            path.chmod(0o644)
            with self.assertRaisesRegex(ValueError, "group or others"):
                load_bearer_token(path)


if __name__ == "__main__":
    unittest.main()
