# codex-vm

`codex-vm` is a local, forge-independent test lab for running repository builds
and release-package tests in versioned environments hosted by disposable
virtual machines. The VM is the security and cleanup boundary. Linux uses
privileged containers; Windows Home uses copy-on-write VM layers and native
execution. The public job configuration and worker protocol are the same.

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
  +-- selected versioned environment           |
  |     Linux: privileged OCI container         |
  |     Windows: pre-provisioned VM disk layer  |
  +-- test process and job file areas           |
        +---------------------------------------+
```

Every environment has a stable `reference` and immutable definition `digest`.
The Linux worker resolves those fields as an OCI image. A Windows worker checks
them against the manifest baked into its selected qcow2 environment layer.
Platform-specific deployment data remains in the environment catalog rather
than the job submitted by a user.

## What works in this baseline

- Create source archives from any local Git repository without forge access.
- Submit a versioned job description and checksum-declared inputs over HTTP.
- Protect the API with mutual TLS when certificate arguments are supplied.
- Pull and run a digest-pinned privileged Linux environment image.
- Verify and run a native Windows Home environment baked into a disposable VM
  layer, without Docker, containerd, Hyper-V, or nested virtualization.
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

The environment sees these logical areas:

| Area | Linux container | Native Windows variable | Access |
| --- | --- | --- | --- |
| Input | `/job/input` | `CODEX_VM_INPUT` | read-only by convention |
| Workspace | `/job/workspace` | `CODEX_VM_WORKSPACE` | read/write |
| Scratch | `/job/scratch` | `CODEX_VM_SCRATCH` | read/write |
| Output | `/job/output` | `CODEX_VM_OUTPUT` | read/write |

Every regular file placed in the output directory is returned as an artifact.

## Environment contract

An environment contains every dependency except the test object. Its command
must write results to `/job/output` on Linux or the directory named by
`CODEX_VM_OUTPUT` on Windows. The job schema does not expose whether an
environment is deployed as an OCI image, qcow2 layer, or a future platform
mechanism.

Example images are under [`environments/`](environments/). They are intentionally
minimal demonstrations; production Topal images should pin compiler, SDK,
packaging, VS Code, and test-harness versions in their own lock manifests.

## Provisioning

The Linux script prepares a container-capable Ubuntu template. Windows Home is
prepared without container support:

1. Run `provisioning/windows/build-base.sh --iso SOURCE`. It downloads HTTPS
   sources when needed, creates a QEMU/OVMF/swtpm VM, installs Windows Home
   unattended, and opens a visible in-guest activation prompt.
2. The guest bootstrap invokes `install-worker.ps1`. Its default `Prompt` mode
   securely asks for a product key and passes it directly to Windows activation
   without putting it in host arguments, answer files, configuration, or build
   artifacts. An empty answer attempts an existing digital license.
3. After the VM shuts down and the operator confirms success, the builder seals
   the base disk while retaining its stable UUID, OVMF variables, and TPM state.
4. Create an environment overlay, install its dependencies, and run
   `set-environment.ps1` with the catalog reference and definition digest.
5. Shut down and retain that environment layer read-only.
6. Create each disposable job disk with
   `provisioning/windows/new-job-overlay.sh ENVIRONMENT.qcow2 JOB.qcow2`.

Use `-ActivationMode DigitalLicense` to suppress the key prompt and attempt
account/hardware-based activation, or `-ActivationMode Skip` when activation
will be completed manually. A digital license is not an alternate key value;
the only secret accepted by the script is a 25-character Windows product key.

Activation belongs to the stable base VM, not a job clone. Reuse the same VM
UUID, virtual TPM state, and virtual hardware definition for sequential job
overlays. Concurrent clones require separate Windows licenses and identities.

Image boot, TLS injection, address discovery, and final deletion remain behind
the planned hypervisor-provider interface. [`config/environments.example.json`](config/environments.example.json)
shows how both deployment kinds are hidden behind the same reference/digest
selection.

## System engineering baseline

[`se/README.md`](se/README.md) is the entry point for stakeholder needs,
requirements, architecture, interfaces, verification, validation, risk,
change control, and traceability. Stable IDs in code and tests connect this
implementation to that baseline.
