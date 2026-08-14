# Windows Home image workflow

Windows Home workers execute directly in a disposable VM overlay. They do not
install Docker, containerd, Hyper-V, WSL, or the Windows Containers feature.

## 1. Prepare the stable base

Obtain a temporary direct ISO link from Microsoft's official
[Windows 11 download page](https://www.microsoft.com/software-download/windows11),
or use the download link from a Windows order confirmation. The Microsoft
retail links expire, so the repository does not contain a permanent ISO URL.

From the repository root, run:

```sh
provisioning/windows/build-base.sh \
  --iso 'https://temporary-download-link.example/Windows.iso' \
  --output work/windows-home-base
```

`--iso` can instead name an existing local ISO. Add `--iso-sha256 HEX` when a
trusted checksum is available. Some order-confirmation links open a web page
rather than returning the ISO itself; in that case, download the ISO in a
browser and pass its local path. Before creating or booting the VM, the builder
verifies that the supplied file is ISO 9660 media with a valid El Torito catalog
and a bootable UEFI entry. The builder downloads a checksum-pinned Python
embeddable ZIP and expands it as the worker's private runtime,
creates a qcow2 disk, unique UUID and MAC, writable OVMF variable store, and
persistent software TPM 2.0 state, and then starts QEMU/KVM with Secure Boot.
It uses SATA storage and an emulated Intel network adapter, so Windows Setup
does not need a separate VirtIO driver ISO.

QEMU shows two DVD devices during base construction. The first is the bootable
Windows installation ISO. The second is the generated `CODEXVM_PAYLOAD` ISO
containing the answer file, bootstrap scripts, worker source, and private Python
runtime; it is deliberately separate so the original Windows media is not
modified.

Windows Setup selects `Windows 11 Home`, partitions the disk, creates a random
temporary `codex-build` administrator, and logs it in once. A visible
PowerShell window then asks for the product key. The key is entered inside the
VM and is never passed through the Linux shell, QEMU command line, answer file,
provisioning ISO, or manifest. After activation and worker installation, the VM
shuts down. Confirm success in the host terminal to seal the base disk.

For an ISO containing Windows 10 instead, explicitly select its image name:

```sh
provisioning/windows/build-base.sh \
  --iso /path/to/Windows10.iso \
  --edition 'Windows 10 Home' \
  --output work/windows-10-home-base
```

Use `--prepare-only` to download and construct all artifacts without booting a
VM. `build-base.sh --help` lists memory, CPU, disk, display, accelerator, OVMF,
and checksum options. Required host commands are QEMU (`qemu-system-x86_64` and
`qemu-img`), `swtpm`, `genisoimage`, `curl`, `openssl`, and Python 3. KVM is
strongly recommended; the TCG fallback is much slower.

The completed directory contains:

- `windows-home-base.qcow2`, sealed read-only after confirmation;
- `vm.conf`, containing the stable virtual hardware identity;
- `OVMF_VARS.fd` and `tpm/`, which must remain with that identity;
- `manifest.json`, containing component hashes and provisioning status;
- `build-user-password`, a generated recovery credential stored with mode
  `0600`.

Environment and job overlays must be booted with this same identity,
sequentially, for one Windows license.

### Manual guest-only alternative

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
short-lived `C:\ProgramData\codex-vm\secrets\controller.token`, and start it
with a loopback-only host forward, for example:

```sh
provisioning/windows/run-vm.sh \
  --vm-dir work/windows-home-base \
  --disk work/topal-package-test-job-1234.qcow2 \
  --worker-port 18443
```

The launcher uses QEMU `restrict=on`; the guest cannot reach the host or
Internet, while `127.0.0.1:18443` on the host reaches guest port 8443. Submit
the common REST job using the same token, then delete the child overlay and
token after artifact collection. The selected environment layer remains
unchanged and can be reused for the next job. `--internet` is reserved for
base provisioning and cannot be combined with `--worker-port`.

The current repository does not yet contain the QEMU provider that boots and
destroys these disks; that provider must also enforce the requested CPU,
memory, disk, lifetime, and test-network policy.
