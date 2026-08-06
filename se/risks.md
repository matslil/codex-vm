# Risk register

Probability and consequence are qualitative for this proposed baseline.

| ID | Risk | Probability | Consequence | Mitigation / evidence | Status |
| --- | --- | --- | --- | --- | --- |
| `LAB-RISK-001` | Privileged test code escapes the guest VM. | Low | Critical | Patched hypervisor, minimal devices, external network policy, disposable clones, hostile-workload validation. | Open |
| `LAB-RISK-002` | A VM obtains a reusable registry or management credential. | Medium | High | Pull-only short-lived tokens, prepare before test execution, never inject hypervisor/forge secrets. | Open |
| `LAB-RISK-003` | Malicious result names or archives compromise the controller. | Medium | High | Treat results as data, validate names/digests/sizes, bound streaming transfer, safe extraction, never execute automatically. | Regular files mitigated; archive extraction open |
| `LAB-RISK-004` | Windows container behavior differs from supported desktop Windows. | Medium | Medium | State the verified container base explicitly; add VM-level desktop checks when product behavior requires them. | Accepted for initial CLI scope |
| `LAB-RISK-005` | Container image tag mutation prevents reproduction. | Medium | High | Require SHA-256 digest in every job and retain immutable registry content. | Mitigated in protocol |
| `LAB-RISK-006` | VM cleanup fails after worker/controller loss. | Medium | High | Idempotent provider delete and independent host-side maximum-lifetime watchdog. | Open until providers exist |
| `LAB-RISK-007` | Source archive omits submodule or LFS content. | Medium | Medium | Declare baseline limitation; implement explicit source assembly before such repositories are supported. | Open |
| `LAB-RISK-008` | Windows and Linux runtime command behavior drifts. | Medium | Medium | One Python protocol/model, platform-specific runtime tests, native demonstrations. | Partly mitigated |
| `LAB-RISK-009` | Huge Windows image layers exhaust local storage. | High | Medium | Quotas, registry retention policy, sparse/differencing disks, curated VM cache. | Open |
| `LAB-RISK-010` | Worker API is exposed beyond the control network. | Low | High | Bind to host-only NIC, mandatory mTLS, external firewall, per-VM certificate. | Partly mitigated |
