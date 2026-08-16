# System requirements

Each requirement has a verification method and initial status. **Approved**
means implemented intent is suitable for baseline approval; merging this change
is the maintainer's approval action. **Proposed** marks deferred behavior.

## Source and forge independence

### LAB-REQ-SRC-001 — Local committed source

The controller shall create a source object from an explicitly selected commit
in a local Git repository without requiring the worker to contact a Git forge.

Verification: test and inspection  
Status: approved

### LAB-REQ-SRC-002 — Source provenance

The controller shall record the Git commit, tree, archive size, and SHA-256
digest for each source archive.

Verification: test  
Status: approved

### LAB-REQ-SRC-003 — Complex repositories

The controller shall eventually support explicit assembly of Git submodule and
Git LFS content without granting forge credentials to workers.

Verification: test  
Status: proposed

## Environment configuration

### LAB-REQ-ENV-001 — Complete environment

An environment artifact shall contain all build or test dependencies except
the test object and explicitly declared inputs.

Verification: demonstration and inspection  
Status: approved

### LAB-REQ-ENV-002 — Immutable selection

Every job shall select its environment using a platform-neutral reference and
a valid SHA-256 environment-definition digest rather than a mutable tag alone.

Verification: test  
Status: approved

### LAB-REQ-ENV-003 — Independent evolution

Environment artifacts shall be versioned independently. Linux OCI images shall
evolve independently from Linux golden VMs. Windows environment layers shall
retain their base-image provenance, and previously referenced digests shall not
be overwritten.

Verification: inspection  
Status: approved

### LAB-REQ-ENV-004 — Read-only distribution

The disposable VM shall obtain Linux images from its inherited cache or a
registry interface that grants no push or delete authority. The Windows
provisioner shall open its selected environment layer read-only and place all
job writes in a disposable child overlay.

Verification: inspection and demonstration  
Status: proposed

### LAB-REQ-ENV-005 — Deployment abstraction

The same environment reference/digest fields and job protocol shall select an
OCI environment on Linux and a native VM-layer environment on Windows without
requiring the job author to configure a runtime backend.

Verification: test and inspection  
Status: approved for worker selection; provider resolution remains proposed

## Job protocol and artifacts

### LAB-REQ-API-001 — Common protocol

Linux and Windows workers shall expose the same versioned HTTP REST protocol
for health, job creation, input upload, start, status, cancellation, and result
download.

Verification: test  
Status: approved

### LAB-REQ-API-002 — Ephemeral controller authorization

Provisioned local worker APIs shall require a unique, time-limited bearer token
injected into each VM clone and shall be reachable only through a host-loopback
forward. Mutual TLS may be used for transports without equivalent isolation.

Verification: test and inspection  
Status: approved

### LAB-REQ-ART-001 — Declared inputs

The worker shall accept only input names, sizes, kinds, and digests declared by
the job before it starts.

Verification: test  
Status: approved

### LAB-REQ-ART-002 — Atomic verification

The worker shall expose an input to the environment only after atomically
receiving and verifying its declared byte length and SHA-256 digest.

Verification: test  
Status: approved

### LAB-REQ-ART-003 — Result provenance

The worker shall report every returned regular file with a name, kind, byte
length, and SHA-256 digest.

Verification: test  
Status: approved

### LAB-REQ-ART-004 — Safe result ingestion

The controller shall treat returned paths and archives as untrusted, enforce
resource limits, and prevent path or symlink escape during extraction.

Verification: test and analysis  
Status: approved for regular-file transfer; archive extraction remains proposed

## Execution and lifecycle

### LAB-REQ-JOB-001 — Isolated job lifecycle

The worker shall run at most one active job and shall create separate input,
workspace, scratch, output, and log areas for it.

Verification: test  
Status: approved

### LAB-REQ-JOB-002 — Container privilege

Linux environments shall be permitted to run as privileged containers, and
native Windows environments shall be permitted to run with administrator
authority, because the disposable VM is the security boundary.

Verification: inspection  
Status: approved

### LAB-REQ-JOB-003 — Terminal evidence

Every started job shall reach a durable succeeded, failed, cancelled, or timed
out state and retain available logs and artifacts until VM destruction.

Verification: test  
Status: approved

### LAB-REQ-JOB-004 — Resource bounds

The worker shall enforce declared CPU, memory, input-size, and wall-time bounds.

Verification: test and inspection  
Status: approved

### LAB-REQ-IO-002 — File-area quota

The provisioner or container runtime shall eventually enforce the declared
aggregate disk bound on job file areas.

Verification: test and demonstration  
Status: proposed

### LAB-REQ-JOB-005 — Disposable VM

The provisioner shall create each job VM from a versioned golden image using
disposable storage and shall delete it after collection or watchdog expiry.

Verification: demonstration  
Status: proposed

## Storage and networking

### LAB-REQ-IO-001 — Stable file areas

Environment runtimes shall receive stable, documented input, workspace,
scratch, and output locations. Linux shall mount input read-only. Windows shall
identify areas through stable environment variables; because administrator
test code can override guest permissions, verified controller-side source
objects remain the integrity reference.

Verification: test and inspection  
Status: approved

### LAB-REQ-NET-001 — Default isolation

A job without an explicit network request shall run its Linux environment
without a container network or its Windows VM without a test-network adapter.

Verification: test and inspection  
Status: approved

### LAB-REQ-NET-002 — Job-local network

A job requesting network communication shall receive a unique network deleted
after execution.

Verification: test and inspection  
Status: approved

### LAB-REQ-NET-003 — Multi-instance topology

The worker shall eventually support multiple named environment instances,
service discovery, readiness checks, and shared job-local storage.

Verification: test and demonstration  
Status: proposed

## Security and operability

### LAB-REQ-SEC-001 — External enforcement

Protection of the physical host, management interfaces, other jobs, and
external networks shall be enforced outside the disposable VM.

Verification: analysis and demonstration  
Status: proposed

### LAB-REQ-SEC-002 — Secret minimization

The disposable VM shall not receive forge, Codex, hypervisor, or reusable
private credentials.

Verification: inspection  
Status: approved

### LAB-REQ-OPS-001 — Platform scope

The initial implementation shall support a Python worker with privileged OCI
execution on Intel Linux and native execution in layered Intel Windows Home
VMs.

Verification: test and demonstration  
Status: approved

### LAB-REQ-OPS-003 — Windows Home provisioning

Windows provisioning shall not require Hyper-V or the Windows Containers
feature. It shall securely prompt for an optional product key, support an
existing digital license or deferred manual activation, and shall not persist
the operator-entered activation key in repository configuration, build
artifacts, or process arguments. The unattended answer file may contain only a
public generic setup key that selects the requested Home edition and cannot
activate Windows.

The Linux-hosted base builder shall accept a local Windows ISO or download one
from an operator-supplied HTTPS URL, install the selected Home edition using
QEMU, Secure Boot-capable OVMF, and a persistent software TPM 2.0 identity, and
shall automate all Windows Setup pages before placing the activation-key prompt
inside the guest session.

The base builder shall not ask the operator to classify the provisioning
network. It shall select a non-discoverable Public profile while retaining
outbound connectivity and Windows Firewall protection.

Base construction shall not require a timed operator keypress to enter Windows
Setup. The builder shall preserve the supplied ISO, derive and hash a no-prompt
UEFI installer from boot images contained in that ISO, and remove the installer
DVD from the VM on Setup's first reset so subsequent boots select the system
disk.

For desktop IDE environments, provisioning shall support running the worker in
a dedicated test user's interactive session rather than Session 0.

Verification: inspection and demonstration  
Status: approved by inspection; native demonstration proposed

### LAB-REQ-OPS-002 — Local operation

Build and test orchestration shall not depend on GitHub Actions or another
hosted continuous-integration service.

Verification: inspection  
Status: approved
