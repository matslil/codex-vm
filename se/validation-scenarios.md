# Validation scenarios

Validation asks whether the system solves stakeholder problems rather than only
whether its implementation conforms to requirements.

## LAB-VAL-001 — Autonomous local Topal change

Given a Codex-created local Topal commit, the operator selects a Linux build
environment, produces a release package, installs that package in a fresh test
environment, receives evidence, and publishes the source change only after the
local result is acceptable. No hosted CI service or worker forge credential is
used.

Success criteria:

- one command can initiate the chain after worker providers exist;
- every report identifies source commit/tree and environment digest;
- failure logs are sufficient for Codex to make the next code change;
- all disposable worker VMs are removed.

Stakeholder needs: `LAB-NEED-001`, `LAB-NEED-003`, `LAB-NEED-004`.

## LAB-VAL-002 — Reproduce an historical failure

The maintainer supplies a previous source commit, environment digest, job
message, and input package. The lab reproduces the environment and obtains the
same material outcome or explicitly reports that a referenced artifact has been
retired contrary to policy.

Success criteria:

- no mutable `latest` reference participates;
- the resolved environment definition and artifact digests equal historical evidence;
- result differences are attributable to recorded external assumptions.

Stakeholder needs: `LAB-NEED-002`.

## LAB-VAL-003 — Upgrade compiler environment

The environment maintainer publishes a new compiler OCI image or Windows VM
layer without deleting the previous artifact. The same source is tested against
both digests and produces independently retained evidence.

Stakeholder needs: `LAB-NEED-002`, `LAB-NEED-005`.

## LAB-VAL-004 — Client/server program

A future multi-instance job starts a server, waits for readiness, then starts a
client on the job-local network. Neither instance can reach another job or the
management network.

Stakeholder needs: `LAB-NEED-006`.

## LAB-VAL-005 — Compromised privileged test

A deliberately hostile privileged Linux container or Windows administrator
process takes control of its VM. It cannot reach hypervisor management, another
job, forge credentials, or the physical LAN. The host watchdog deletes the VM
after its deadline.

Stakeholder needs: `LAB-NEED-004`.
