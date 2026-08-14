# Stakeholders and needs

## LAB-STK-001 — Repository maintainer

The maintainer needs reproducible evidence that a committed change builds and
that its release package installs and behaves correctly on supported systems.

## LAB-STK-002 — Autonomous coding agent

Codex needs a local, scriptable facility that accepts exact repository state,
runs tests without interactive intervention, returns actionable evidence, and
does not depend on one Git forge.

## LAB-STK-003 — Test environment maintainer

The environment maintainer needs build tools, IDE dependencies, and test
harnesses to be independently versioned, quickly replaceable, and historically
reproducible.

## LAB-STK-004 — Lab operator

The operator needs physical hosts, credentials, networks, and old job state to
remain protected when repository-controlled test code is privileged inside its
environment.

## LAB-STK-005 — Developer and reviewer

Developers and reviewers need an exact association between source revision,
environment digest, release artifact, logs, results, and verification claims.

## Stakeholder needs

| ID | Need | Stakeholders |
| --- | --- | --- |
| `LAB-NEED-001` | Run local tests without GitHub Actions or forge coupling. | `LAB-STK-001`, `LAB-STK-002` |
| `LAB-NEED-002` | Reproduce old builds using immutable environment versions. | `LAB-STK-001`, `LAB-STK-003`, `LAB-STK-005` |
| `LAB-NEED-003` | Exchange source, release packages, status, logs, and results through one small interface. | `LAB-STK-002`, `LAB-STK-005` |
| `LAB-NEED-004` | Treat the disposable VM as the security and cleanup boundary. | `LAB-STK-004` |
| `LAB-NEED-005` | Start test environments quickly without reinstalling dependencies. | `LAB-STK-002`, `LAB-STK-003` |
| `LAB-NEED-006` | Exercise file and network communication between test processes. | `LAB-STK-001`, `LAB-STK-005` |
