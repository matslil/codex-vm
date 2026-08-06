# Concept of operations

## LAB-CONOPS-001 — Nominal build and test flow

1. The controller identifies a committed local Git revision.
2. It creates a source archive and provenance manifest.
3. A provisioner clones a Linux or Windows golden VM image using a disposable
   disk and injects a unique mutual-TLS identity.
4. The VM starts its worker API on a host-only control network.
5. The controller submits a job naming a container image and immutable digest.
6. The worker obtains that image from its cache or a read-only local registry.
7. The controller uploads the declared test object and starts the job.
8. The worker starts the privileged environment container with read-only input
   and writable workspace, scratch, and output areas.
9. The controller monitors state while the container builds or tests.
10. The worker returns checksummed packages, logs, and results.
11. The controller orders the provisioner to power off and delete the VM clone.
12. A host-side watchdog performs deletion if normal control is lost.

## LAB-CONOPS-002 — Build-to-install chain

A build job consumes a source archive and returns the native release package.
A separate job in a fresh VM consumes that release package and tests its native
installation, operation, upgrade, or removal. Intermediate executables may
exist, but the final installation test consumes the package delivered to users.

## LAB-CONOPS-003 — Trust model

Repository-controlled code and privileged containers are untrusted. All
containers belonging to one job may trust each other. The disposable VM is the
security boundary; hypervisor networking and host-side lifecycle controls must
remain effective after complete guest compromise.

The VM receives no forge, Codex, hypervisor, or reusable private credentials.
Registry access is read-only and preferably short-lived. Returned artifacts are
untrusted data until the controller validates their names, sizes, and digests.

## LAB-CONOPS-004 — Environment evolution

Environment definitions are reviewed source. Published images are immutable
and selected by digest. Common images may be cached in golden VM images, while
an external local registry remains authoritative. Updating a container does not
require invalidating an older environment or rebuilding the VM immediately.

## Off-nominal behavior

- Missing or corrupt input is rejected before execution.
- A pull or runtime failure marks the job failed and preserves logs.
- A timeout stops the container and marks the job timed out.
- Cancellation requests stop the container and mark the job cancelled.
- Loss of the worker causes the controller or watchdog to destroy the VM.
- Loss of the controller is bounded by the host-side VM lifetime limit.

