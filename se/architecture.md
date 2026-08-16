# Logical architecture

## Components

| ID | Component | Responsibility |
| --- | --- | --- |
| `LAB-CMP-001` | Local controller | Exports Git state, chooses environments, provisions workers, submits jobs, validates results, and destroys workers. |
| `LAB-CMP-002` | Provisioner adapter | Clones a golden image, injects identity/configuration, reports its address, and destroys it. |
| `LAB-CMP-003` | Hypervisor boundary | Isolates disposable guests and enforces control/test network policy outside them. |
| `LAB-CMP-004` | Worker API | Validates messages and artifacts, persists job state, and controls the runtime. |
| `LAB-CMP-005` | Environment runtime adapter | Uses a privileged OCI runtime on Linux or verifies and executes the baked native environment on Windows. |
| `LAB-CMP-006` | Environment artifact | Supplies all dependencies and a test harness while accepting the test object at runtime. |
| `LAB-CMP-007` | Environment artifact store | Stores immutable Linux OCI images and read-only Windows VM layers. |
| `LAB-CMP-008` | Artifact store | Retains source, release packages, logs, results, and provenance outside disposable guests. |

## Deployment views

### Linux

```text
Linux hypervisor
└── disposable Intel Ubuntu VM
    ├── worker API
    ├── Docker-compatible runtime
    └── privileged Linux environment container
```

### Windows

```text
Windows-capable hypervisor
└── stable Windows Home base identity and environment qcow2 layer
    └── disposable per-job qcow2 overlay
    ├── worker API
    ├── native environment manifest and dependencies
    └── administrator test process
        └── optional dedicated interactive session for desktop IDE automation
```

Windows uses no inner container runtime or nested virtualization. The Linux
hypervisor supplies the security boundary, while qcow2 backing chains provide
versioning and fast disposal. Sequential job clones retain the licensed base
VM's UUID and virtual TPM identity.

## Data flow

```text
Git commit --archive--> source object
source object --authenticated HTTP--> build environment
build environment --authenticated HTTP--> release package
release package --authenticated HTTP--> clean package-test environment
test environment --authenticated HTTP--> evidence bundle
```

## Architecture decisions

### LAB-ADR-001 — VM security boundary

The disposable VM, not the container, is the security boundary. This permits
privileged test environments and makes cleanup independent of guest behavior.

### LAB-ADR-002 — Containers for configuration

Linux containers and Windows copy-on-write VM layers package independently
versioned tools and harnesses and are selected by immutable definition digest.

### LAB-ADR-003 — Pull before test execution

The Linux worker prepares the environment image before starting
repository-controlled code so registry credentials can be absent during
execution. The Windows provisioner selects a read-only environment layer before
the worker boots, and the worker verifies its embedded manifest.

### LAB-ADR-004 — Common Python worker

A pinned Python runtime and standard-library implementation provide one worker
protocol on Linux and Windows with a small dependency and bootstrap surface.

### LAB-ADR-005 — Controller-initiated local HTTP

The controller initiates communication through a random loopback-bound host
port forwarded to one worker VM. A high-entropy bearer token binds requests to
that VM lifetime. Hypervisor policy blocks other guest-to-host and external
traffic. Mutual TLS remains optional for non-local transports.

### LAB-ADR-006 — Platform-specific deployment behind one contract

Jobs name an environment reference and digest without selecting a backend.
Catalog metadata maps Linux to OCI and Windows Home to a qcow2 environment
layer. Future macOS deployment can add another catalog kind without changing
the worker REST protocol or job authoring model.

### LAB-ADR-007 — Activation only in the Windows base

A product key or digital-license operation is performed interactively while
constructing the stable Windows base. Keys are never job inputs. Environment
and job overlays inherit activation while retaining the same virtual hardware
identity; one license is not used for concurrent clones.

The base builder creates a random one-time local administrator credential for
unattended OOBE and stores its recovery value only in the mode-`0600` VM state
directory. The purchased Windows product key is entered either into the visible
guest PowerShell prompt or passed explicitly to the host builder. In the latter
case, it is transported on a separate private temporary activation medium that
is excluded from durable build outputs and removed by the host cleanup trap.
