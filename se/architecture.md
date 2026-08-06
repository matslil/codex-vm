# Logical architecture

## Components

| ID | Component | Responsibility |
| --- | --- | --- |
| `LAB-CMP-001` | Local controller | Exports Git state, chooses environments, provisions workers, submits jobs, validates results, and destroys workers. |
| `LAB-CMP-002` | Provisioner adapter | Clones a golden image, injects identity/configuration, reports its address, and destroys it. |
| `LAB-CMP-003` | Hypervisor boundary | Isolates disposable guests and enforces control/test network policy outside them. |
| `LAB-CMP-004` | Worker API | Validates messages and artifacts, persists job state, and controls the runtime. |
| `LAB-CMP-005` | Container runtime adapter | Pulls a pinned image and runs, stops, and cleans the environment container/network. |
| `LAB-CMP-006` | Environment image | Supplies all dependencies and a test harness while accepting the test object at runtime. |
| `LAB-CMP-007` | Read-only registry | Stores immutable Linux and Windows environment images. |
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
└── disposable Intel Windows VM
    ├── worker API
    ├── Windows container runtime
    ├── Windows environment container as ContainerAdministrator
    └── VS Code host installation for future Dev Container tests
```

Process-isolated Windows containers share the disposable guest kernel. Hyper-V
container isolation is optional because the outer VM supplies the boundary.

## Data flow

```text
Git commit --archive--> source object
source object --HTTPS--> build environment
build environment --HTTPS--> release package
release package --HTTPS--> clean package-test environment
test environment --HTTPS--> evidence bundle
```

## Architecture decisions

### LAB-ADR-001 — VM security boundary

The disposable VM, not the container, is the security boundary. This permits
privileged test environments and makes cleanup independent of guest behavior.

### LAB-ADR-002 — Containers for configuration

Containers package independently versioned tools and harnesses because their
layers start quickly and can be selected by immutable digest.

### LAB-ADR-003 — Pull before test execution

The worker prepares the environment image before starting repository-controlled
code so registry credentials can be absent during execution.

### LAB-ADR-004 — Common Python worker

A pinned Python runtime and standard-library implementation provide one worker
protocol on Linux and Windows with a small dependency and bootstrap surface.

### LAB-ADR-005 — Controller-initiated HTTPS

The controller initiates communication to a worker API on a host-only network.
Mutual TLS binds each connection to the controller and one ephemeral VM.

