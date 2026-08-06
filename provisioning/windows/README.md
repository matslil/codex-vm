# Windows Home image workflow

Windows Home workers execute directly in a disposable VM overlay. They do not
install Docker, containerd, Hyper-V, WSL, or the Windows Containers feature.

## 1. Prepare the stable base

Install Windows Home in a QEMU/KVM qcow2 disk. Configure one persistent virtual
machine identity and retain its UUID, virtual TPM state, firmware variables,
disk-controller model, CPU model, and MAC address. Environment and job overlays
must be booted with that same identity, sequentially, for one Windows license.

Build the Python wheel outside the guest and make the wheel and a Python
installer/runtime available to the guest. From an elevated interactive
PowerShell prompt run:

```powershell
Set-ExecutionPolicy -Scope Process RemoteSigned
.\install-worker.ps1 -Python C:\staging\python.exe `
    -Wheel C:\staging\codex_vm-0.1.0-py3-none-any.whl
```

That default installs a headless startup task running as `SYSTEM`. For an
environment that automates the VS Code desktop, install the worker into the
dedicated desktop test user's interactive session instead:

```powershell
.\install-worker.ps1 -Python C:\staging\python.exe `
    -Wheel C:\staging\codex_vm-0.1.0-py3-none-any.whl `
    -WorkerSession Interactive -WorkerUser codex-test
```

The image must arrange an interactive logon for `codex-test` before the worker
can accept a GUI job. Do not use a real person's account or password. A
headless `SYSTEM` process runs in Session 0 and therefore cannot provide valid
desktop-IDE evidence.

If Windows is not already activated, the default `Prompt` mode asks for a
25-character product key using `Read-Host -AsSecureString`. Leaving it empty
attempts automatic activation from an existing digital license. Alternatives:

```powershell
.\install-worker.ps1 ... -ActivationMode DigitalLicense
.\install-worker.ps1 ... -ActivationMode Skip
```

There is no separate “activation key” input. A purchased serial in a Windows
order confirmation is normally called a product key. A digital license has no
string to enter; it is resolved by Microsoft's activation service and, when
necessary, the interactive Activation troubleshooter.

Before sealing the base, confirm activation in **Settings > System >
Activation**. Do not put a product key in an unattended XML file, command-line
argument, repository file, environment manifest, or image-building log.

## 2. Build a versioned environment layer

Create an overlay backed by the sealed base, boot it using the stable VM
identity, and install all dependencies except the package or source under test.
The example native environment can be provisioned with:

```powershell
C:\staging\provision.ps1 `
    -Reference topal/package-test-windows-home-x64/2026.08.0 `
    -Digest sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb `
    -SetEnvironmentScript C:\staging\set-environment.ps1 `
    -VsCodeSystemInstaller C:\staging\VSCodeSetup-x64.exe
```

The digest identifies the reviewed environment definition. Separately record
the SHA-256 of the completed qcow2 artifact in the environment catalog. Shut
Windows down cleanly and make the completed parent image read-only by policy.

## 3. Deploy a disposable job

On the Linux hypervisor host:

```sh
provisioning/windows/new-job-overlay.sh \
  images/topal-package-test-windows-home-x64-2026.08.0.qcow2 \
  work/topal-package-test-job-1234.qcow2
```

Boot that small overlay with the stable Windows identity, inject only its
short-lived worker TLS material, and submit the same REST job schema used for a
Linux worker. Delete the child overlay after artifact collection. The selected
environment layer remains unchanged and can be reused for the next job.

The current repository does not yet contain the QEMU provider that boots and
destroys these disks; that provider must also enforce the requested CPU,
memory, disk, lifetime, and test-network policy.
