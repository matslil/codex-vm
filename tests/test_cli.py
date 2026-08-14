from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codex_vm.cli import main


class WorkerCLIHardeningTests(unittest.TestCase):
    def test_requires_authentication_by_default(self) -> None:
        with self.assertRaisesRegex(SystemExit, "bearer token or mutual TLS"):
            main(["serve", "--host", "127.0.0.1"])

    def test_never_allows_unauthenticated_non_loopback_service(self) -> None:
        with self.assertRaisesRegex(SystemExit, "only on loopback"):
            main(["serve", "--host", "0.0.0.0", "--insecure-no-auth"])

    def test_creates_a_controller_token_without_printing_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "controller.token"
            self.assertEqual(main(["create-token", str(path)]), 0)
            self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
