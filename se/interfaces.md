# System interfaces

## LAB-IF-001 — Worker REST API

Protocol version 1 uses HTTP/1.1 and JSON metadata. Provisioned deployments use
TLS with mandatory client certificates.

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
`500`.

## LAB-IF-002 — Environment runtime contract

The worker invokes the environment's configured entry point followed by the
job `command` arguments. It mounts:

| Logical area | Linux | Windows | Mode |
| --- | --- | --- | --- |
| input | `/job/input` | `C:\job\input` | read-only |
| workspace | `/job/workspace` | `C:\job\workspace` | read/write |
| scratch | `/job/scratch` | `C:\job\scratch` | read/write |
| output | `/job/output` | `C:\job\output` | read/write |

Every regular, non-symlink file at the output root becomes a result artifact.

## LAB-IF-003 — Registry

The runtime uses the OCI/Docker Registry pull interface. A job supplies a
repository name and SHA-256 manifest digest. Authorization, when needed, is
limited to pull and expires before or shortly after environment preparation.

## LAB-IF-004 — Provisioner

The planned controller/provider boundary is:

```python
create(base_image, job_id, identity, resources, network_policy) -> Worker
wait_ready(worker, deadline) -> Endpoint
destroy(worker) -> None
```

The provider implementation owns hypervisor-specific commands and must make
`destroy` idempotent.

## LAB-IF-005 — Source archive

The baseline source object is a gzip-compressed Git archive of one commit with
a manifest containing commit ID, tree ID, byte length, and SHA-256 digest. It
does not contain `.git`, uncommitted files, submodule contents, or implicitly
downloaded Git LFS objects.

