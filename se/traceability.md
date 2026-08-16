# Bidirectional traceability

## Needs to requirements

| Need | Requirements |
| --- | --- |
| `LAB-NEED-001` | `LAB-REQ-SRC-001`, `LAB-REQ-OPS-002` |
| `LAB-NEED-002` | `LAB-REQ-SRC-002`, `LAB-REQ-ENV-002`, `LAB-REQ-ENV-003`, `LAB-REQ-ART-003` |
| `LAB-NEED-003` | `LAB-REQ-API-001`, `LAB-REQ-API-002`, `LAB-REQ-ENV-005`, `LAB-REQ-ART-001`, `LAB-REQ-ART-002`, `LAB-REQ-ART-003` |
| `LAB-NEED-004` | `LAB-REQ-JOB-001`, `LAB-REQ-JOB-002`, `LAB-REQ-JOB-005`, `LAB-REQ-SEC-001`, `LAB-REQ-SEC-002` |
| `LAB-NEED-005` | `LAB-REQ-ENV-001`, `LAB-REQ-ENV-003`, `LAB-REQ-ENV-004`, `LAB-REQ-ENV-005`, `LAB-REQ-OPS-003` |
| `LAB-NEED-006` | `LAB-REQ-IO-001`, `LAB-REQ-NET-001`, `LAB-REQ-NET-002`, `LAB-REQ-NET-003` |

## Requirements to architecture, implementation, and verification

| Requirement | Architecture/interfaces | Implementation | Verification |
| --- | --- | --- | --- |
| `LAB-REQ-SRC-001` | `LAB-CMP-001`, `LAB-IF-005` | `controller.git_archive` | `LAB-VER-007` |
| `LAB-REQ-SRC-002` | `LAB-IF-005` | `controller.git_archive` | `LAB-VER-007` |
| `LAB-REQ-SRC-003` | `LAB-IF-005` | Deferred | Gap |
| `LAB-REQ-ENV-001` | `LAB-CMP-006`, `LAB-ADR-002` | `environments/` examples | `LAB-VER-012` |
| `LAB-REQ-ENV-002` | `LAB-ADR-002`, `LAB-IF-003` | `models.EnvironmentSpec`, `runtime.DockerRuntime`, `runtime.NativeRuntime` | `LAB-VER-001`, `LAB-VER-006`, `LAB-VER-014` |
| `LAB-REQ-ENV-003` | `LAB-CMP-007`, `LAB-ADR-002` | Environment catalog example | Inspection |
| `LAB-REQ-ENV-004` | `LAB-CMP-007`, `LAB-ADR-003`, `LAB-IF-003` | Pull supported; authorization deferred | Gap |
| `LAB-REQ-ENV-005` | `LAB-ADR-006`, `LAB-IF-003`, `LAB-IF-004` | Common `EnvironmentSpec`; automatic platform runtime | `LAB-VER-014`; provider gap |
| `LAB-REQ-API-001` | `LAB-CMP-004`, `LAB-IF-001` | `api.py`, `controller.WorkerClient` | `LAB-VER-003` |
| `LAB-REQ-API-002` | `LAB-ADR-005`, `LAB-IF-001` | `api.serve`, provisioning services | `LAB-VER-008` |
| `LAB-REQ-ART-001` | `LAB-IF-001` | `models.InputSpec`, `manager.upload` | `LAB-VER-001`, `LAB-VER-002` |
| `LAB-REQ-ART-002` | `LAB-IF-001` | `security.receive_verified` | `LAB-VER-002` |
| `LAB-REQ-ART-003` | `LAB-IF-001`, `LAB-IF-002` | `manager._collect_artifacts` | `LAB-VER-004` |
| `LAB-REQ-ART-004` | `LAB-ADR-001` | Bounded atomic download verification; extraction deferred | Partial |
| `LAB-REQ-JOB-001` | `LAB-CMP-004` | `manager.JobManager`, `store.JobStore` | `LAB-VER-005` |
| `LAB-REQ-JOB-002` | `LAB-ADR-001`, `LAB-IF-002` | `runtime.DockerRuntime`, `runtime.NativeRuntime` | `LAB-VER-006`, `LAB-VER-014` |
| `LAB-REQ-JOB-003` | `LAB-CMP-004` | `manager._execute`, `store.JobStore` | `LAB-VER-004` |
| `LAB-REQ-JOB-004` | `LAB-IF-001`, `LAB-IF-002` | Model validation, upload limit, Docker limits | `LAB-VER-002`, `LAB-VER-006` |
| `LAB-REQ-JOB-005` | `LAB-CMP-002`, `LAB-CMP-003` | Provisioning scripts only | `LAB-VER-009`, `LAB-VER-010` |
| `LAB-REQ-IO-001` | `LAB-IF-002` | `store.JobStore`, both runtime adapters | `LAB-VER-006`, `LAB-VER-014` |
| `LAB-REQ-IO-002` | `LAB-CMP-002`, `LAB-IF-002` | Deferred | Gap |
| `LAB-REQ-NET-001` | `LAB-IF-002`, `LAB-IF-004` | Linux runtime implemented; Windows provider deferred | `LAB-VER-006`; provider gap |
| `LAB-REQ-NET-002` | `LAB-CMP-005` | `runtime.DockerRuntime` | `LAB-VER-006` |
| `LAB-REQ-NET-003` | Planned job-group architecture | Deferred | Gap |
| `LAB-REQ-SEC-001` | `LAB-CMP-003`, `LAB-ADR-001` | Hypervisor provider deferred | `LAB-VER-011` |
| `LAB-REQ-SEC-002` | `LAB-ADR-003`, `LAB-ADR-005` | Protocol contains no privileged credentials | Inspection |
| `LAB-REQ-OPS-001` | Linux and Windows deployment views, `LAB-ADR-006` | Runtime and provisioning platform branches | `LAB-VER-009`, `LAB-VER-010`, `LAB-VER-014` |
| `LAB-REQ-OPS-002` | `LAB-CMP-001` | Local controller; no hosted CI integration | Inspection |
| `LAB-REQ-OPS-003` | Windows deployment view, `LAB-ADR-007`, `LAB-CONOPS-005` | Validated no-prompt media derivation, QMP reset/eject manager, `provisioning/windows/`, `runtime.NativeRuntime` | `LAB-VER-014`, `LAB-VER-015`, `LAB-VER-016` |

## Validation coverage

| Validation scenario | Needs |
| --- | --- |
| `LAB-VAL-001` | `LAB-NEED-001`, `LAB-NEED-003`, `LAB-NEED-004` |
| `LAB-VAL-002` | `LAB-NEED-002` |
| `LAB-VAL-003` | `LAB-NEED-002`, `LAB-NEED-005` |
| `LAB-VAL-004` | `LAB-NEED-006` |
| `LAB-VAL-005` | `LAB-NEED-004` |

## Maintenance rules

- Every approved requirement has implementation evidence or an explicit gap.
- Every automated verification case identifies the requirements it supports.
- Requirements do not become validated merely because their tests pass.
- New externally observable behavior updates this matrix in the same change.
