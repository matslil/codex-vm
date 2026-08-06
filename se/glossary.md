# Glossary

| Term | Meaning |
| --- | --- |
| Artifact | A checksummed input or output file crossing the VM boundary. |
| Controller | Trusted local process coordinating source export, provisioning, jobs, and evidence. |
| Environment | Immutable container image containing tools, dependencies, and harnesses but not the test object. |
| Forge | Git collaboration service such as GitHub, GitLab, or Forgejo. |
| Golden image | Versioned VM template cloned to create disposable workers. |
| Job | One declared operation and its inputs, environment, resources, state, and results. |
| Job group | Planned set of cooperating instances sharing one trust boundary, network, and optional storage. |
| Registry | Local OCI/Docker image distribution service with read-only worker access. |
| Release package | Native distributable object, such as `.deb`, `.msi`, or `.vsix`, tested as delivered. |
| Test object | Source archive, release package, or plugin supplied at job time rather than baked into an environment. |
| Worker | Disposable VM and its small control service. |

