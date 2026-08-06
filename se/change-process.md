# Baseline and change process

## Change sequence

1. Identify affected stakeholder needs, requirements, interfaces, risks, and
   validation scenarios.
2. Propose new or changed text using stable IDs.
3. Update architecture and interface decisions before implementation when the
   external contract changes.
4. Implement the smallest coherent behavior and its verification evidence.
5. Update `traceability.md` and `verification-report.md`.
6. Record commands and gaps in the pull request.
7. Obtain human maintainer review before merge.

## Stable ID rules

- Never reuse an ID for unrelated meaning.
- Mark withdrawn statements `retired` and retain their historical text or a
  pointer to the superseding statement.
- A requirement change that invalidates old evidence must update traceability.
- Architecture decisions use `LAB-ADR-*`; interfaces use `LAB-IF-*`;
  verification cases use `LAB-VER-*`; validation scenarios use `LAB-VAL-*`.

## Environment configuration control

- Human-friendly environment versions are metadata; digests are execution
  identity.
- Publishing new content at a previously used digest is structurally impossible
  and registry retention must prevent deleting referenced manifests.
- VM image versions record OS revision, worker version, runtime version, and
  cached image digests.
- An environment update is reviewed like source and produces a new digest.

## Compatibility changes

An incompatible worker protocol change introduces a new `/vN/` namespace. A
new controller may support multiple worker protocol versions during migration.
An incompatible environment runtime contract receives a new contract version
in environment metadata.

