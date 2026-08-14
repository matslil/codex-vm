#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: run-vm.sh --vm-dir DIR [--disk DISK] [--cdrom ISO ...]
                 [--boot-cdrom] [--display TYPE]

Boot a Windows VM using the stable UUID, MAC address, OVMF variables, and TPM
state recorded in DIR/vm.conf. DISK defaults to DIR/windows-home-base.qcow2.
EOF
}

vm_dir=""
disk=""
display="gtk"
boot_cdrom=false
cdroms=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --vm-dir) vm_dir=${2:?missing --vm-dir value}; shift 2 ;;
        --disk) disk=${2:?missing --disk value}; shift 2 ;;
        --cdrom) cdroms+=("${2:?missing --cdrom value}"); shift 2 ;;
        --boot-cdrom) boot_cdrom=true; shift ;;
        --display) display=${2:?missing --display value}; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) echo "unknown argument: $1" >&2; usage >&2; exit 64 ;;
    esac
done

[[ -n "$vm_dir" ]] || { usage >&2; exit 64; }
vm_dir=$(realpath "$vm_dir")
config="$vm_dir/vm.conf"
[[ -f "$config" ]] || { echo "missing VM configuration: $config" >&2; exit 66; }

read_config() {
    local key=$1 value
    value=$(sed -n "s/^${key}=//p" "$config")
    [[ -n "$value" ]] || { echo "missing $key in $config" >&2; exit 65; }
    printf '%s\n' "$value"
}

uuid=$(read_config VM_UUID)
mac=$(read_config VM_MAC)
memory_mb=$(read_config VM_MEMORY_MB)
cpus=$(read_config VM_CPUS)
accel=$(read_config VM_ACCEL)
cpu_model=$(read_config VM_CPU_MODEL)
ovmf_code=$(read_config VM_OVMF_CODE)
ovmf_vars=$(read_config VM_OVMF_VARS)
[[ -n "$disk" ]] || disk="$vm_dir/windows-home-base.qcow2"
disk=$(realpath "$disk")

[[ "$uuid" =~ ^[0-9a-fA-F-]{36}$ ]] || { echo "invalid VM UUID" >&2; exit 65; }
[[ "$mac" =~ ^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$ ]] || { echo "invalid VM MAC" >&2; exit 65; }
[[ "$memory_mb" =~ ^[0-9]+$ ]] || { echo "invalid VM memory" >&2; exit 65; }
[[ "$cpus" =~ ^[0-9]+$ ]] || { echo "invalid VM CPU count" >&2; exit 65; }
[[ "$accel" == "kvm" || "$accel" == "tcg" ]] || { echo "invalid accelerator" >&2; exit 65; }
[[ "$display" =~ ^[A-Za-z0-9,=._-]+$ ]] || { echo "invalid display type" >&2; exit 65; }
for path in "$disk" "$ovmf_code" "$ovmf_vars" "${cdroms[@]}"; do
    [[ -f "$path" ]] || { echo "VM artifact does not exist: $path" >&2; exit 66; }
done

qemu=${QEMU_SYSTEM_X86_64:-qemu-system-x86_64}
swtpm=${SWTPM:-swtpm}
command -v "$qemu" >/dev/null || { echo "missing command: $qemu" >&2; exit 69; }
command -v "$swtpm" >/dev/null || { echo "missing command: $swtpm" >&2; exit 69; }

tpm_dir="$vm_dir/tpm"
socket="$vm_dir/swtpm.sock"
pid_file="$vm_dir/swtpm.pid"
mkdir -p "$tpm_dir"
rm -f "$socket" "$pid_file"

cleanup() {
    if [[ -f "$pid_file" ]]; then
        read -r pid < "$pid_file" || true
        if [[ "${pid:-}" =~ ^[0-9]+$ ]]; then
            kill "$pid" 2>/dev/null || true
        fi
    fi
    rm -f "$socket" "$pid_file"
}
trap cleanup EXIT INT TERM

"$swtpm" socket --tpm2 --tpmstate "dir=$tpm_dir,lock" \
    --ctrl "type=unixio,path=$socket,terminate" --pid "file=$pid_file" --daemon

arguments=(
    -name codex-windows-home
    -machine "q35,smm=on,accel=$accel"
    -cpu "$cpu_model"
    -m "$memory_mb"
    -smp "$cpus"
    -uuid "$uuid"
    -global driver=cfi.pflash01,property=secure,value=on
    -drive "if=pflash,format=raw,unit=0,readonly=on,file=$ovmf_code"
    -drive "if=pflash,format=raw,unit=1,file=$ovmf_vars"
    -device ich9-ahci,id=sata
    -drive "if=none,id=osdisk,format=qcow2,cache=writeback,discard=unmap,file=$disk"
    -device ide-hd,drive=osdisk,bus=sata.0,bootindex=1
    -chardev "socket,id=chrtpm,path=$socket"
    -tpmdev emulator,id=tpm0,chardev=chrtpm
    -device tpm-crb,tpmdev=tpm0
    -netdev user,id=net0
    -device "e1000e,netdev=net0,mac=$mac"
    -device qemu-xhci
    -device usb-tablet
    -vga std
    -display "$display"
)

index=1
for iso in "${cdroms[@]}"; do
    iso=$(realpath "$iso")
    arguments+=(
        -drive "if=none,id=cdrom$index,format=raw,media=cdrom,readonly=on,file=$iso"
        -device "ide-cd,drive=cdrom$index,bus=sata.$index,bootindex=$((index + 1))"
    )
    index=$((index + 1))
done
if $boot_cdrom; then
    arguments+=(-boot menu=on,once=d)
else
    arguments+=(-boot menu=on)
fi

"$qemu" "${arguments[@]}"
