# System interfaces

## LAB-IF-001 — Worker REST API

Protocol version 1 uses HTTP/1.1 and JSON metadata. Provisioned local VMs require
a unique bearer token and expose the guest port only through a host-loopback
forward. Mutual TLS is optional for transports without equivalent isolation.

| Method and path | Purpose | Success |
| --- | --- | --- |
| `GET /v1/health` | Report readiness and protocol version. | `200` |
| `POST /v1/jobs` | Validate and create the one VM job. | `201` |
| `PUT /v1/jobs/{id}/inputs/{name}` | Atomically receive one declared input. | `200` |
| `POST /v1/jobs/{id}/start` | Prepare the image and execute asynchronously. | `202` |
| `GET /v1/jobs/{id}` | Return durable state and artifact metadata. | `200` |
| `POST /v1/jobs/{id}/cancel` | Request runtime cancellation. | `202` |
| `GET /v1/jobs/{id}/artifacts/{name}` | Stream one declared result. | `200` |

Errors are JSON objects containing `error`. Validation errors return `400`,
unknown objects `404`, state conflicts `409`, and unexpected worker failures
return a generic `500`. Missing or incorrect authentication returns `401`.

## LAB-IF-002 — Environment runtime contract

The worker invokes the job `command` in the selected environment. Linux mounts
fixed paths; native Windows supplies absolute paths through environment
variables:

| Logical area | Linux | Native Windows | Mode |
| --- | --- | --- | --- |
| input | `/job/input` | `CODEX_VM_INPUT` | read-only mount / verified source area |
| workspace | `/job/workspace` | `CODEX_VM_WORKSPACE` | read/write |
| scratch | `/job/scratch` | `CODEX_VM_SCRATCH` | read/write |
| output | `/job/output` | `CODEX_VM_OUTPUT` | read/write |

Every regular, non-symlink file with a protocol-safe name at the output root
becomes a result artifact. Aggregate input and output transfer limits are
enforced independently from the planned disk-area quota.

## LAB-IF-003 — Environment artifact store

The catalog gives every platform a common `reference` and definition `digest`.
Linux deployment uses the OCI/Docker Registry pull interface and combines those
fields as `reference@digest`. Windows deployment maps them to a qcow2 artifact
with its own file SHA-256, uses that file as a read-only backing image, and
creates a per-job child overlay. Registry authorization, when needed, is
limited to pull and expires before or shortly after environment preparation.

## LAB-IF-004 — Provisioner

The planned controller/provider boundary is:

```python
create(environment, job_id, identity, resources, network_policy) -> Worker
wait_ready(worker, deadline) -> Endpoint
destroy(worker) -> None
```

The provider implementation owns hypervisor-specific commands and must make
`destroy` idempotent. It resolves the catalog's platform-specific `deployment`
object; callers do not branch on `oci`, `qcow2`, or future deployment kinds.

## LAB-IF-005 — Source archive

The baseline source object is a gzip-compressed Git archive of one commit with
a manifest containing commit ID, tree ID, byte length, and SHA-256 digest. It
does not contain `.git`, uncommitted files, submodule contents, or implicitly
downloaded Git LFS objects.
