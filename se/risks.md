# Risk register

Probability and consequence are qualitative for this proposed baseline.

| ID | Risk | Probability | Consequence | Mitigation / evidence | Status |
| --- | --- | --- | --- | --- | --- |
| `LAB-RISK-001` | Privileged test code escapes the guest VM. | Low | Critical | Patched hypervisor, minimal devices, external network policy, disposable clones, hostile-workload validation. | Open |
| `LAB-RISK-002` | A VM obtains a reusable registry or management credential. | Medium | High | Pull-only short-lived tokens, prepare before test execution, never inject hypervisor/forge secrets. | Open |
| `LAB-RISK-003` | Malicious result names or archives compromise the controller. | Medium | High | Treat results as data, validate names/digests/sizes, bound streaming transfer, safe extraction, never execute automatically. | Regular files mitigated; archive extraction open |
| `LAB-RISK-004` | Native Windows VM layers are larger and slower to rebuild than containers. | High | Medium | Sparse qcow2 backing chains, immutable curated layers, local SSD cache, and per-job overlays. | Mitigated by architecture; measurement open |
| `LAB-RISK-005` | Container image tag mutation prevents reproduction. | Medium | High | Require SHA-256 digest in every job and retain immutable registry content. | Mitigated in protocol |
| `LAB-RISK-006` | VM cleanup fails after worker/controller loss. | Medium | High | Idempotent provider delete and independent host-side maximum-lifetime watchdog. | Open until providers exist |
| `LAB-RISK-007` | Source archive omits submodule or LFS content. | Medium | Medium | Declare baseline limitation; implement explicit source assembly before such repositories are supported. | Open |
| `LAB-RISK-008` | Windows and Linux runtime command behavior drifts. | Medium | Medium | One Python protocol/model, platform-specific runtime tests, native demonstrations. | Partly mitigated |
| `LAB-RISK-009` | Huge Windows image layers exhaust local storage. | High | Medium | Quotas, registry retention policy, sparse/differencing disks, curated VM cache. | Open |
| `LAB-RISK-010` | Worker API is exposed beyond the control network. | Low | High | QEMU `restrict=on`, loopback-only explicit forwarding, per-VM token, mandatory authentication, optional mTLS for non-local transports. | Mitigated in launcher and worker; provider demonstration open |
| `LAB-RISK-011` | Recreated virtual hardware invalidates Windows activation. | Medium | High | Activate only the stable base; retain VM UUID, virtual TPM state, and hardware definition; do not concurrently clone one licensed identity. | Demonstration open |
| `LAB-RISK-012` | A Windows product key leaks through automation. | Low | High | Secure interactive prompt, CIM activation call, no key parameter, no unattended-file or repository persistence. | Mitigated by inspection |
| `LAB-RISK-013` | A Session 0 worker produces invalid desktop-IDE evidence. | Medium | High | Provision GUI environments with the dedicated-user interactive task mode; retain SYSTEM mode only for headless jobs. | Mitigated by design; demonstration open |
| `LAB-RISK-014` | Unattended Windows setup exposes its temporary local account credential. | Low | Medium | Generate a unique random value per base, restrict the VM state directory and recovery file to the operator, remove autologon and cached answer files after bootstrap, and never reuse the account outside the disposable VM boundary. | Mitigated by implementation; Windows inspection open |
| `LAB-RISK-015` | Expired or replaced download links make a base irreproducible or return an HTML page in place of installation media. | Medium | Medium | Accept local media, validate the ISO 9660 and El Torito structures plus a bootable UEFI entry, optionally require expected SHA-256 values, retain downloaded media locally, and record actual component hashes in the base manifest. | Mitigated by implementation |
| `LAB-RISK-016` | Timed DVD prompts or persistent installer priority prevent unattended Windows installation or restart Setup after its first reboot. | High | Medium | Derive a hashed UEFI installer using Microsoft's included no-prompt image, start QEMU paused under QMP control, and eject only the installer DVD on the first guest reset. | Mitigated by implementation; native demonstration open |
