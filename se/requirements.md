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

An environment image shall contain all build or test dependencies except the
test object and explicitly declared inputs.

Verification: demonstration and inspection  
Status: approved

### LAB-REQ-ENV-002 — Immutable selection

Every job shall select its environment using a container image name and a valid
SHA-256 image digest rather than a mutable tag alone.

Verification: test  
Status: approved

### LAB-REQ-ENV-003 — Independent evolution

Environment images shall be versioned independently from golden VM images, and
previously referenced digests shall not be overwritten.

Verification: inspection  
Status: approved

### LAB-REQ-ENV-004 — Read-only distribution

The disposable VM shall obtain environment images from its inherited cache or
a registry interface that grants no push or delete authority.

Verification: inspection and demonstration  
Status: proposed

## Job protocol and artifacts

### LAB-REQ-API-001 — Common protocol

Linux and Windows workers shall expose the same versioned HTTPS REST protocol
for health, job creation, input upload, start, status, cancellation, and result
download.

Verification: test  
Status: approved

### LAB-REQ-API-002 — Mutual authentication

Provisioned worker APIs shall require mutually authenticated TLS using a unique,
time-limited identity injected into each VM clone.

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

Linux environments shall be permitted to run privileged, and Windows
environments shall be permitted to run with administrator authority, because
the disposable VM is the security boundary.

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

Environment containers shall receive stable, documented input, workspace,
scratch, and output locations with input mounted read-only.

Verification: test and inspection  
Status: approved

### LAB-REQ-NET-001 — Default isolation

A job without an explicit network request shall run its environment container
without a container network.

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

The initial implementation shall support Python worker execution and container
launch construction on Intel Linux and Intel Windows.

Verification: test and demonstration  
Status: approved

### LAB-REQ-OPS-002 — Local operation

Build and test orchestration shall not depend on GitHub Actions or another
hosted continuous-integration service.

Verification: inspection  
Status: approved
