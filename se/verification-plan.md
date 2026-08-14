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
| `LAB-VER-006` | Test | Linux Docker command construction pins the digest, mounts input read-only, applies limits, and selects privileged execution. |
| `LAB-VER-007` | Test | Git archive provenance identifies the selected commit/tree and matches archive size/digest. |
| `LAB-VER-008` | Test | A provisioned worker rejects an absent or incorrect ephemeral token; unauthenticated mode is restricted to explicit loopback development use. |
| `LAB-VER-009` | Demonstration | Linux golden image boots, pulls a cached/new image, runs a job, and is deleted. |
| `LAB-VER-010` | Demonstration | Windows Home retains activation and environment identity through base, environment, and disposable job qcow2 layers. |
| `LAB-VER-011` | Analysis | Hypervisor network policy remains effective after guest administrator compromise. |
| `LAB-VER-012` | Demonstration | A build package becomes the input of a fresh installation-test job. |
| `LAB-VER-013` | Test and demonstration | Job file areas cannot exceed their declared aggregate disk bound. |
| `LAB-VER-014` | Test | Native execution rejects a mismatched environment manifest and exposes stable job paths without a container engine. |
| `LAB-VER-015` | Inspection and demonstration | Windows provisioning prompts securely for a product key, supports digital-license/skip and headless/interactive modes, and starts a native worker without container features. |
| `LAB-VER-016` | Test and demonstration | The Windows base builder validates inputs, derives and hashes no-prompt UEFI media without changing the source, prepares immutable provenance and stable VM identity, constructs unattended payload/qcow2 artifacts without exposing a product key, and launches QEMU with OVMF Secure Boot and software TPM 2.0. QMP starts the paused VM and ejects the installer on its first guest reset; actual installation remains a native demonstration. |

## Evidence rules

- Automated tests reference applicable requirement IDs where the relationship
  is not evident from the traceability matrix.
- Demonstrations record image IDs/digests, commands, timestamps, and results.
- A verification failure is not waived by rebuilding an environment. It is
  resolved, accepted by the maintainer, or recorded as a baseline gap.
- Linux demonstrations use a native container engine. Windows demonstrations
  execute directly in the selected Windows Home VM layer. Emulation is not
  final platform evidence.
- Verification evidence never establishes stakeholder fitness by itself;
  validation scenarios do that.
