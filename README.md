# codex-vm

`codex-vm` is a local, forge-independent test lab for running repository builds
and release-package tests inside versioned containers hosted by disposable
virtual machines. The VM is the security and cleanup boundary. Containers are
allowed to be privileged and exist to make test environments quick to start,
immutable, and independently versioned.

This first implementation concentrates on Intel Linux and Intel Windows. macOS,
iOS, Android, hypervisor providers, multi-container topologies, and automated
certificate issuance remain planned extensions.

## Architecture

```text
local Git repository
        |
        | git archive
        v
controller -----------------------------------+
        |                                      |
        | provision copy-on-write VM           |
        | HTTPS with mutual TLS                 |
        v                                      |
disposable Linux or Windows VM                 |
  +-- small Python worker REST API             |
  +-- container runtime                        |
  +-- cached environment images                |
  +-- privileged test container                |
        +-- read-only input                     |
        +-- writable workspace/scratch/output   |
        +-- optional job-local network          |
        +---------------------------------------+
```

The container image is selected by an immutable digest. A read-only local
registry is the intended source of truth; commonly used layers may be cached in
the VM template. The worker pulls and verifies the selected image before it
starts repository-controlled code.

## What works in this baseline

- Create source archives from any local Git repository without forge access.
- Submit a versioned job description and checksum-declared inputs over HTTP.
- Protect the API with mutual TLS when certificate arguments are supplied.
- Pull a digest-pinned environment image.
- Run a privileged Linux container or a `ContainerAdministrator` Windows
  container with CPU, memory, timeout, storage, and optional network controls.
- Persist job state atomically and expose status through the REST API.
- Return checksummed build products and logs.
- Cancel or time out jobs.
- Provision the common worker software on Ubuntu and Windows templates.

The HTTP-only mode exists for local tests. Provisioned workers must use mutual
TLS and bind the service only to a host-only control interface.

## Install for development

```sh
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m unittest discover -v
```

On Windows, use `.venv\Scripts\python.exe`.

## Create a source object

Only committed Git state is exported. A controller that needs to test
uncommitted Codex changes should first create a temporary local commit/ref.

```sh
codex-vm archive ../topal work/topal-source.tar.gz --revision HEAD
```

The command prints the commit, tree, size, and SHA-256 provenance metadata.
Submodules and Git LFS objects require explicit source assembly and are not yet
handled by this baseline exporter.

## Start a development worker

The following non-TLS form is only for loopback development:

```sh
codex-vm serve --root work --host 127.0.0.1 --port 8443
```

Production VM template invocation:

```sh
codex-vm serve \
  --root /var/lib/codex-vm \
  --host 192.0.2.10 \
  --port 8443 \
  --certificate /run/codex-vm/worker.crt \
  --private-key /run/codex-vm/worker.key \
  --client-ca /run/codex-vm/controller-ca.crt
```

Certificates are injected into each VM clone and must not be stored in the
golden image.

## Submit a job

See [`config/job.example.json`](config/job.example.json). After adjusting its
input digest and size:

```sh
codex-vm submit https://worker:8443 config/job.example.json \
  --ca certificates/ca.crt \
  --certificate certificates/controller.crt \
  --private-key certificates/controller.key \
  --input source=work/topal-source.tar.gz \
  --results work/results
```

The environment container sees these stable locations:

| Area | Linux | Windows | Access |
| --- | --- | --- | --- |
| Input | `/job/input` | `C:\job\input` | read-only |
| Workspace | `/job/workspace` | `C:\job\workspace` | read/write |
| Scratch | `/job/scratch` | `C:\job\scratch` | read/write |
| Output | `/job/output` | `C:\job\output` | read/write |

Every regular file placed in the output directory is returned as an artifact.

## Environment contract

An environment image contains every dependency except the test object. Its
entry command receives the job-specific operation arguments from `command` and
must write results to `/job/output` or `C:\job\output`.

Example images are under [`environments/`](environments/). They are intentionally
minimal demonstrations; production Topal images should pin compiler, SDK,
packaging, VS Code, and test-harness versions in their own lock manifests.

## Provisioning

The scripts under [`provisioning/`](provisioning/) prepare golden images. Image
construction itself is hypervisor-specific and intentionally outside the first
baseline. A future provider interface will clone these images, inject the
per-VM TLS identity, discover the control address, and delete the clone after
result collection or a watchdog timeout.

## System engineering baseline

[`se/README.md`](se/README.md) is the entry point for stakeholder needs,
requirements, architecture, interfaces, verification, validation, risk,
change control, and traceability. Stable IDs in code and tests connect this
implementation to that baseline.

