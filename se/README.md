# codex-vm system engineering

This directory is the authoritative systems-engineering baseline for the local
disposable test lab. It uses a deliberately small subset of INCOSE practice:
stakeholder identification, concept of operations, needs and requirements,
logical architecture, controlled interfaces, verification, validation, risk,
configuration management, and bidirectional traceability.

- [Stakeholders](stakeholders.md)
- [Concept of operations](concept-of-operations.md)
- [Requirements](requirements.md)
- [Architecture](architecture.md)
- [Interfaces](interfaces.md)
- [Verification plan](verification-plan.md)
- [Verification report](verification-report.md)
- [Validation scenarios](validation-scenarios.md)
- [Risk register](risks.md)
- [Traceability](traceability.md)
- [Change process](change-process.md)
- [Glossary](glossary.md)

The keywords **shall**, **should**, and **may** express mandatory behavior,
recommended behavior, and permitted variation. Stable IDs are permanent. A
retired statement keeps its ID and is marked retired rather than being removed
or reused for unrelated meaning.

## Baseline status

This first baseline is **proposed**. It covers Intel Linux and Intel Windows,
one active job per disposable VM, one primary environment container per job,
local Git source export, digest-pinned environment selection, and HTTPS worker
communication. The human maintainer approves this baseline by merging it.

## Scope boundaries

Included:

- forge-independent local source export;
- controller-to-worker protocol;
- disposable VM and versioned container responsibilities;
- build and release-package test artifact exchange;
- job-scoped files and a basic container network;
- Linux privileged and Windows administrator container execution;
- verification and operational evidence.

Deferred:

- macOS, iOS, Android, and ARM64 workers;
- concrete libvirt, Hyper-V, Proxmox, and cloud provisioner adapters;
- automatic PKI issuance;
- multiple primary test containers and cross-host test networks;
- Git submodule and Git LFS source assembly;
- VS Code automation and Topal-specific environment definitions.

