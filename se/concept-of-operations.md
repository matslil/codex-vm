# Concept of operations

## LAB-CONOPS-001 — Nominal build and test flow

1. The controller identifies a committed local Git revision.
2. It creates a source archive and provenance manifest.
3. A provisioner clones a Linux or Windows golden VM image using a disposable
   disk and injects a unique high-entropy API token.
4. The VM starts its worker API behind a random loopback-only host forward.
5. The controller resolves a platform-neutral environment reference and digest.
6. Linux pulls the selected OCI image. Windows boots a disposable overlay of
   the corresponding pre-provisioned VM layer and verifies its manifest.
7. The controller uploads the declared test object and starts the job.
8. The worker starts the privileged Linux container or native Windows process
   with input, workspace, scratch, and output areas.
9. The controller monitors state while the environment builds or tests.
10. The worker returns checksummed packages, logs, and results.
11. The controller orders the provisioner to power off and delete the VM clone.
12. A host-side watchdog performs deletion if normal control is lost.

## LAB-CONOPS-002 — Build-to-install chain

A build job consumes a source archive and returns the native release package.
A separate job in a fresh VM consumes that release package and tests its native
installation, operation, upgrade, or removal. Intermediate executables may
exist, but the final installation test consumes the package delivered to users.

## LAB-CONOPS-003 — Trust model

Repository-controlled code, privileged containers, and native administrator
processes are untrusted. The disposable VM is the security boundary;
hypervisor networking and host-side lifecycle controls must remain effective
after complete guest compromise.

The VM receives no forge, Codex, hypervisor, or reusable private credentials.
Registry access is read-only and preferably short-lived. Returned artifacts are
untrusted data until the controller validates their names, sizes, and digests.

## LAB-CONOPS-004 — Environment evolution

Environment definitions are reviewed source. Published OCI images and qcow2
environment layers are immutable and selected by definition digest. Updating
one environment does not invalidate older environments. Windows layers record
their base provenance so an environment can be rebuilt after base updates.

## LAB-CONOPS-005 — Windows base construction

The operator supplies a local Windows ISO or temporary official HTTPS download
URL to the Linux-hosted builder. It creates the disk and stable virtual hardware
identity, derives a hashed no-prompt installer while retaining the original
media, and installs Windows Home unattended. The host ejects the installer at
Setup's first reset, then pauses in a visible guest PowerShell session for
product-key entry. Successful activation and worker installation shut down the
guest; explicit host confirmation seals the base. The purchased key never
crosses the guest boundary.

## Off-nominal behavior

- Missing or corrupt input is rejected before execution.
- A pull, manifest mismatch, or runtime failure marks the job failed and preserves logs.
- A timeout stops the environment process and marks the job timed out.
- Cancellation requests stop the environment process and mark the job cancelled.
- Loss of the worker causes the controller or watchdog to destroy the VM.
- Loss of the controller is bounded by the host-side VM lifetime limit.
