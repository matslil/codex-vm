from __future__ import annotations

import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from codex_vm.models import ValidationError
from codex_vm.security import receive_verified, sha256_file
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


if __name__ == "__main__":
    unittest.main()
