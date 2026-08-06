# Verification plan

## Methods

| Method | Meaning |
| --- | --- |
| Test | Automated unit or integration evidence with deterministic acceptance criteria. |
| Inspection | Review of code, configuration, image definition, or documentation. |
| Analysis | Reasoned security, performance, or compatibility argument with assumptions. |
| Demonstration | Controlled operation on a representative Linux or Windows VM. |

## Command baseline

```sh
python3 -m compileall -q src tests
PYTHONPATH=src python3 -m unittest discover -v
ruff check .
ruff format --check .
mypy
```

`scripts/check.sh` runs the available subset. Missing optional tools shall be
reported rather than silently treated as passing.

## Planned verification cases

| ID | Method | Acceptance criterion |
| --- | --- | --- |
| `LAB-VER-001` | Test | Invalid job IDs, input names, digests, resources, and duplicate inputs are rejected. |
| `LAB-VER-002` | Test | A matching upload appears atomically; truncated, corrupt, and oversize uploads do not. |
| `LAB-VER-003` | Test | REST health, create, upload, start, status, and artifact download complete. |
| `LAB-VER-004` | Test | A successful runtime produces terminal state, logs, result metadata, size, and digest. |
| `LAB-VER-005` | Test | A second active job is rejected. |
| `LAB-VER-006` | Test | Docker command construction pins the digest, mounts input read-only, applies limits, and selects platform privilege. |
| `LAB-VER-007` | Test | Git archive provenance identifies the selected commit/tree and matches archive size/digest. |
| `LAB-VER-008` | Test | Mutual TLS rejects an untrusted or absent client certificate. |
| `LAB-VER-009` | Demonstration | Linux golden image boots, pulls a cached/new image, runs a job, and is deleted. |
| `LAB-VER-010` | Demonstration | Windows golden image performs the equivalent Windows-container lifecycle. |
| `LAB-VER-011` | Analysis | Hypervisor network policy remains effective after guest administrator compromise. |
| `LAB-VER-012` | Demonstration | A build package becomes the input of a fresh installation-test job. |
| `LAB-VER-013` | Test and demonstration | Job file areas cannot exceed their declared aggregate disk bound. |

## Evidence rules

- Automated tests reference applicable requirement IDs where the relationship
  is not evident from the traceability matrix.
- Demonstrations record image IDs/digests, commands, timestamps, and results.
- A verification failure is not waived by rebuilding an environment. It is
  resolved, accepted by the maintainer, or recorded as a baseline gap.
- Windows and Linux demonstrations use native container engines on their target
  VM; emulation is not final platform evidence.
- Verification evidence never establishes stakeholder fitness by itself;
  validation scenarios do that.
