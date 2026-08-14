#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repository=$(realpath "$script_dir/../..")

usage() {
    cat <<'EOF'
Usage: build-base.sh --iso SOURCE [options]

Download or use a Windows ISO, create a QEMU/OVMF/swtpm Windows Home VM, run
unattended installation, and open a visible in-guest prompt for activation.

Required:
  --iso SOURCE              Local ISO path or temporary HTTPS download URL.

Options:
  --output DIR              VM state directory (default: work/windows-home-base).
  --iso-sha256 HEX          Expected Windows ISO SHA-256.
  --edition NAME            Install image name (default: Windows 11 Home).
  --python-source SOURCE    Python embeddable ZIP path or HTTPS URL.
  --python-sha256 HEX       Expected Python runtime ZIP SHA-256.
  --disk-size SIZE          qcow2 virtual size (default: 80G).
  --memory-mb MB            Guest memory (default: 8192).
  --cpus COUNT              Guest virtual CPUs (default: 4).
  --accel auto|kvm|tcg      QEMU accelerator (default: auto).
  --display TYPE            QEMU display backend (default: gtk).
  --ovmf-code PATH          Secure-boot OVMF code image.
  --ovmf-vars PATH          Secure-boot OVMF variable template.
  --prepare-only            Build artifacts but do not boot QEMU.
  --help                    Show this help.

The Windows product key is intentionally not a host option. Windows asks for it
inside the VM using a secure PowerShell prompt after installation.
EOF
}

iso_source=""
iso_sha256=""
output="work/windows-home-base"
edition="Windows 11 Home"
python_source="https://www.python.org/ftp/python/3.13.14/python-3.13.14-embed-amd64.zip"
python_sha256="90b4e5b9898b72d744650524bff92377c367f44bd5fbd09e3148656c080ad907"
python_source_overridden=false
python_sha256_overridden=false
disk_size="80G"
memory_mb=8192
cpus=4
accel=auto
display=gtk
ovmf_code=""
ovmf_vars=""
prepare_only=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --iso) iso_source=${2:?missing --iso value}; shift 2 ;;
        --iso-sha256) iso_sha256=${2:?missing --iso-sha256 value}; shift 2 ;;
        --output) output=${2:?missing --output value}; shift 2 ;;
        --edition) edition=${2:?missing --edition value}; shift 2 ;;
        --python-source) python_source=${2:?missing --python-source value}; python_source_overridden=true; shift 2 ;;
        --python-sha256) python_sha256=${2:?missing --python-sha256 value}; python_sha256_overridden=true; shift 2 ;;
        --disk-size) disk_size=${2:?missing --disk-size value}; shift 2 ;;
        --memory-mb) memory_mb=${2:?missing --memory-mb value}; shift 2 ;;
        --cpus) cpus=${2:?missing --cpus value}; shift 2 ;;
        --accel) accel=${2:?missing --accel value}; shift 2 ;;
        --display) display=${2:?missing --display value}; shift 2 ;;
        --ovmf-code) ovmf_code=${2:?missing --ovmf-code value}; shift 2 ;;
        --ovmf-vars) ovmf_vars=${2:?missing --ovmf-vars value}; shift 2 ;;
        --prepare-only) prepare_only=true; shift ;;
        --help|-h) usage; exit 0 ;;
        *) echo "unknown argument: $1" >&2; usage >&2; exit 64 ;;
    esac
done

if $python_source_overridden && ! $python_sha256_overridden; then
    python_sha256=""
fi

[[ -n "$iso_source" ]] || { echo "--iso is required" >&2; usage >&2; exit 64; }
edition_pattern='^[A-Za-z0-9_.()[:space:]-]+$'
[[ "$edition" =~ $edition_pattern ]] || { echo "invalid Windows edition name" >&2; exit 65; }
[[ "$disk_size" =~ ^[1-9][0-9]*[GM]$ ]] || { echo "invalid disk size" >&2; exit 65; }
[[ "$memory_mb" =~ ^[0-9]+$ && "$memory_mb" -ge 4096 ]] || { echo "memory must be at least 4096 MiB" >&2; exit 65; }
[[ "$cpus" =~ ^[0-9]+$ && "$cpus" -ge 2 ]] || { echo "at least two CPUs are required" >&2; exit 65; }
[[ "$accel" == auto || "$accel" == kvm || "$accel" == tcg ]] || { echo "invalid accelerator" >&2; exit 65; }
for digest in "$iso_sha256" "$python_sha256"; do
    [[ -z "$digest" || "$digest" =~ ^[0-9a-fA-F]{64}$ ]] || { echo "invalid SHA-256" >&2; exit 65; }
done

qemu_img=${QEMU_IMG:-qemu-img}
iso_builder=${ISO_BUILDER:-genisoimage}
host_python=${HOST_PYTHON:-}
if [[ -z "$host_python" ]]; then
    if [[ -x "$repository/.venv/bin/python" ]]; then
        host_python="$repository/.venv/bin/python"
    else
        host_python=python3
    fi
fi
for command_name in "$qemu_img" "$iso_builder" "$host_python" curl openssl sha256sum realpath; do
    command -v "$command_name" >/dev/null || { echo "missing command: $command_name" >&2; exit 69; }
done

if [[ -z "$ovmf_code" ]]; then
    for candidate in /usr/share/OVMF/OVMF_CODE.secboot.fd /usr/share/edk2/ovmf/OVMF_CODE.secboot.fd; do
        [[ -f "$candidate" ]] && { ovmf_code=$candidate; break; }
    done
fi
if [[ -z "$ovmf_vars" ]]; then
    for candidate in /usr/share/OVMF/OVMF_VARS.secboot.fd /usr/share/edk2/ovmf/OVMF_VARS.secboot.fd; do
        [[ -f "$candidate" ]] && { ovmf_vars=$candidate; break; }
    done
fi
[[ -f "$ovmf_code" ]] || { echo "secure-boot OVMF code image not found" >&2; exit 69; }
[[ -f "$ovmf_vars" ]] || { echo "secure-boot OVMF variable template not found" >&2; exit 69; }
ovmf_code=$(realpath "$ovmf_code")
ovmf_vars=$(realpath "$ovmf_vars")

mkdir -p "$output"
output=$(realpath "$output")
chmod 700 "$output"
downloads="$output/downloads"
mkdir -p "$downloads"
disk="$output/windows-home-base.qcow2"
[[ ! -e "$disk" ]] || { echo "refusing to overwrite existing base disk: $disk" >&2; exit 73; }

staging=$(mktemp -d)
cleanup() {
    rm -rf "$staging"
}
trap cleanup EXIT INT TERM

verify_digest() {
    local path=$1 expected=$2 actual
    actual=$(sha256sum "$path" | cut -d ' ' -f 1)
    if [[ -n "$expected" && "${actual,,}" != "${expected,,}" ]]; then
        echo "SHA-256 mismatch for $path" >&2
        exit 65
    fi
    printf '%s\n' "$actual"
}

obtain() {
    local source=$1 destination=$2 expected=$3
    if [[ -f "$source" ]]; then
        realpath "$source"
        return
    fi
    if [[ "$source" != https://* ]]; then
        echo "source must be an existing file or HTTPS URL: $source" >&2
        exit 65
    fi
    if [[ ! -f "$destination" ]]; then
        echo "Downloading $(basename "$destination")..." >&2
        curl --fail --location --proto '=https' --tlsv1.2 \
            --output "$destination.part" "$source"
        mv "$destination.part" "$destination"
    fi
    verify_digest "$destination" "$expected" >/dev/null
    realpath "$destination"
}

windows_iso=$(obtain "$iso_source" "$downloads/windows.iso" "$iso_sha256")
python_runtime=$(obtain "$python_source" "$downloads/python-3.13.14-embed-amd64.zip" "$python_sha256")
if ! "$host_python" "$script_dir/validate-install-media.py" "$windows_iso"; then
    echo "Use a direct ISO download or a local ISO file; web/download pages are not installation media." >&2
    exit 65
fi
windows_iso_digest=$(verify_digest "$windows_iso" "$iso_sha256")
python_digest=$(verify_digest "$python_runtime" "$python_sha256")
if [[ -z "$iso_sha256" ]]; then
    echo "Warning: no expected Windows ISO SHA-256 was supplied; recorded $windows_iso_digest" >&2
fi
if [[ -z "$python_sha256" ]]; then
    echo "Warning: no expected Python runtime SHA-256 was supplied; recorded $python_digest" >&2
fi

payload="$staging/payload"
mkdir -p "$payload"
cp "$script_dir/install-worker.ps1" "$script_dir/bootstrap.ps1" \
    "$script_dir/bootstrap.cmd" "$payload/"
cp "$python_runtime" "$payload/$(basename "$python_runtime")"
touch "$payload/codex-vm-payload.marker"

mkdir -p "$payload/codex_vm"
while IFS= read -r -d '' source_file; do
    relative=${source_file#"$repository/src/codex_vm/"}
    mkdir -p "$payload/codex_vm/$(dirname "$relative")"
    cp "$source_file" "$payload/codex_vm/$relative"
done < <(find "$repository/src/codex_vm" -type f ! -path '*/__pycache__/*' -print0)
source_digest=$("$host_python" - "$payload/codex_vm" <<'PY'
import hashlib
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
digest = hashlib.sha256()
for path in sorted(item for item in root.rglob("*") if item.is_file()):
    digest.update(path.relative_to(root).as_posix().encode())
    digest.update(b"\0")
    digest.update(path.read_bytes())
print(digest.hexdigest())
PY
)

build_password="Cv!9$(openssl rand -hex 12)"
password_file="$output/build-user-password"
printf '%s\n' "$build_password" > "$password_file"
chmod 600 "$password_file"

sed -e "s|@@WINDOWS_EDITION@@|$edition|g" \
    -e "s|@@BUILD_PASSWORD@@|$build_password|g" \
    "$script_dir/Autounattend.xml.in" > "$payload/Autounattend.xml"
cat > "$payload/bootstrap-config.json" <<EOF
{
  "schema": 1,
  "activation_mode": "Prompt",
  "worker_session": "System",
  "worker_user": "codex-build",
  "python_archive": "$(basename "$python_runtime")"
}
EOF

payload_iso="$output/provisioning.iso"
"$iso_builder" -quiet -J -R -V CODEXVM_PAYLOAD -o "$payload_iso" "$payload"
payload_digest=$(verify_digest "$payload_iso" "")

cp "$ovmf_vars" "$output/OVMF_VARS.fd"
chmod 600 "$output/OVMF_VARS.fd"
mkdir -p "$output/tpm"
chmod 700 "$output/tpm"

vm_uuid=$("$host_python" -c 'import uuid; print(uuid.uuid4())')
mac_suffix=$(printf '%s' "$vm_uuid" | sha256sum | cut -c 1-6)
vm_mac="52:54:00:${mac_suffix:0:2}:${mac_suffix:2:2}:${mac_suffix:4:2}"
if [[ "$accel" == auto ]]; then
    if [[ -r /dev/kvm && -w /dev/kvm ]]; then
        accel=kvm
    else
        accel=tcg
        echo "Warning: /dev/kvm is unavailable; TCG installation will be very slow." >&2
    fi
fi
if [[ "$accel" == kvm ]]; then
    cpu_model=host
else
    cpu_model=max
fi

cat > "$output/vm.conf" <<EOF
VM_UUID=$vm_uuid
VM_MAC=$vm_mac
VM_MEMORY_MB=$memory_mb
VM_CPUS=$cpus
VM_ACCEL=$accel
VM_CPU_MODEL=$cpu_model
VM_OVMF_CODE=$ovmf_code
VM_OVMF_VARS=$output/OVMF_VARS.fd
EOF
chmod 600 "$output/vm.conf"

"$qemu_img" create -f qcow2 "$disk" "$disk_size"

write_manifest() {
    local status=$1
    "$host_python" - "$output/manifest.json" "$status" "$edition" "$vm_uuid" \
        "$vm_mac" "$windows_iso" "$windows_iso_digest" "$python_digest" \
        "$source_digest" "$payload_digest" <<'PY'
import datetime
import json
import pathlib
import sys

(
    destination,
    status,
    edition,
    vm_uuid,
    mac,
    windows_iso,
    windows_iso_sha256,
    python_sha256,
    worker_source_sha256,
    payload_sha256,
) = sys.argv[1:]
value = {
    "schema": 1,
    "status": status,
    "created_at": datetime.datetime.now(datetime.UTC).isoformat(),
    "edition": edition,
    "vm_uuid": vm_uuid,
    "mac": mac,
    "windows_iso": windows_iso,
    "windows_iso_sha256": f"sha256:{windows_iso_sha256}",
    "python_runtime_sha256": f"sha256:{python_sha256}",
    "worker_source_sha256": f"sha256:{worker_source_sha256}",
    "provisioning_iso_sha256": f"sha256:{payload_sha256}",
}
pathlib.Path(destination).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
PY
}

write_manifest prepared
if $prepare_only; then
    echo "Prepared Windows VM artifacts in $output"
    echo "No VM was started because --prepare-only was selected."
    exit 0
fi

echo "Starting Windows Setup. Keep the VM window open."
echo "After installation, Windows will open a PowerShell window asking for the product key."
"$script_dir/run-vm.sh" --vm-dir "$output" --disk "$disk" \
    --cdrom "$windows_iso" --cdrom "$payload_iso" --boot-cdrom --display "$display" \
    --internet

printf 'Did the guest report successful provisioning before it shut down? [y/N] '
read -r confirmed
if [[ "$confirmed" != y && "$confirmed" != Y ]]; then
    echo "The base remains writable and is not marked complete: $disk" >&2
    exit 1
fi

chmod 444 "$disk"
rm -f "$payload_iso"
write_manifest complete
echo "Windows Home base completed: $disk"
echo "Stable VM identity: $output/vm.conf"
echo "Generated build-user password (mode 0600): $password_file"
