# Verification report

Date: 2026-08-06  
Baseline: first implementation attempt  
Status: automated baseline passing; native VM demonstrations deferred

## Requirement verification status

| Verification | Requirements | Evidence | Initial result |
| --- | --- | --- | --- |
| `LAB-VER-001` | `LAB-REQ-ENV-002`, `LAB-REQ-ART-001` | `tests/test_models.py` | Pass |
| `LAB-VER-002` | `LAB-REQ-ART-002`, `LAB-REQ-JOB-004` | `tests/test_security.py` | Pass |
| `LAB-VER-003` | `LAB-REQ-API-001` | `tests/test_api.py` | Pass |
| `LAB-VER-004` | `LAB-REQ-ART-003`, `LAB-REQ-JOB-003` | `tests/test_manager.py` | Pass |
| `LAB-VER-005` | `LAB-REQ-JOB-001` | `tests/test_manager.py` | Pass |
| `LAB-VER-006` | `LAB-REQ-JOB-002`, `LAB-REQ-IO-001`, `LAB-REQ-NET-001`, `LAB-REQ-NET-002` | `tests/test_runtime.py` | Pass |
| `LAB-VER-007` | `LAB-REQ-SRC-001`, `LAB-REQ-SRC-002` | `tests/test_controller.py` | Pass |
| `LAB-VER-008` | `LAB-REQ-API-002` | TLS integration test gap | Pending |
| `LAB-VER-009` | `LAB-REQ-JOB-005`, `LAB-REQ-OPS-001` | Linux VM demonstration | Deferred |
| `LAB-VER-010` | `LAB-REQ-JOB-005`, `LAB-REQ-OPS-001` | Windows VM demonstration | Deferred |
| `LAB-VER-011` | `LAB-REQ-SEC-001`, `LAB-REQ-SEC-002` | Threat-model review | Deferred |
| `LAB-VER-012` | `LAB-REQ-ENV-001`, `LAB-REQ-OPS-002` | Topal build/install demonstration | Deferred |
| `LAB-VER-013` | `LAB-REQ-IO-002` | Quota implementation | Deferred |
| `LAB-VER-014` | `LAB-REQ-ENV-002`, `LAB-REQ-ENV-005`, `LAB-REQ-JOB-002`, `LAB-REQ-IO-001`, `LAB-REQ-OPS-001`, `LAB-REQ-OPS-003` | `tests/test_runtime.py` | Pass |
| `LAB-VER-015` | `LAB-REQ-OPS-003` | `tests/test_provisioning.py`; native demonstration pending | Partial |
| `LAB-VER-016` | `LAB-REQ-OPS-003` | `tests/test_provisioning.py`; real Windows installation pending | Partial |

## Commands run

```text
PYTHONPATH=src python3 -m unittest discover -v
28 tests passed
```

The HTTP integration tests required permission to bind a loopback port outside
the normal repository sandbox. Deferred VM demonstrations require lab
infrastructure not present in the repository baseline.
