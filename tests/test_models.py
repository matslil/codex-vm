from __future__ import annotations

import unittest

from codex_vm.models import JobSpec, ValidationError
from tests.helpers import job_spec


class JobSpecTests(unittest.TestCase):
    def test_rejects_string_network_boolean(self) -> None:
        value = job_spec()
        value["network"] = "false"
        with self.assertRaisesRegex(ValidationError, "network must be a boolean"):
            JobSpec.from_dict(value)

    # LAB-REQ-ENV-002: environment selection is immutable and digest pinned.
    def test_builds_digest_pinned_image(self) -> None:
        spec = JobSpec.from_dict(job_spec())
        self.assertEqual(
            spec.environment.pinned_image,
            f"registry.lab/topal/build-linux-x64@sha256:{'a' * 64}",
        )

    def test_accepts_legacy_image_as_reference(self) -> None:
        value = job_spec()
        environment = value["environment"]
        assert isinstance(environment, dict)
        environment["image"] = environment.pop("reference")
        spec = JobSpec.from_dict(value)
        self.assertEqual(spec.environment.reference, "registry.lab/topal/build-linux-x64")

    def test_rejects_mutable_or_malformed_digest(self) -> None:
        value = job_spec()
        value["environment"]["digest"] = "latest"  # type: ignore[index]
        with self.assertRaisesRegex(ValidationError, "digest"):
            JobSpec.from_dict(value)

    def test_rejects_duplicate_inputs(self) -> None:
        value = job_spec()
        value["inputs"].append(dict(value["inputs"][0]))  # type: ignore[union-attr,index]
        with self.assertRaisesRegex(ValidationError, "unique"):
            JobSpec.from_dict(value)

    def test_rejects_path_like_input_name(self) -> None:
        value = job_spec()
        value["inputs"][0]["name"] = "../source"  # type: ignore[index]
        with self.assertRaisesRegex(ValidationError, "name"):
            JobSpec.from_dict(value)


if __name__ == "__main__":
    unittest.main()
