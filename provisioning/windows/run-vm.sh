#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: run-vm.sh --vm-dir DIR [--disk DISK] [--cdrom ISO ...]
                 [--boot-cdrom] [--display TYPE] [--worker-port PORT]
                 [--internet]

Boot a Windows VM using the stable UUID, MAC address, OVMF variables, and TPM
state recorded in DIR/vm.conf. DISK defaults to DIR/windows-home-base.qcow2.
Networking is isolated by default. --worker-port forwards one loopback-only
host port to guest port 8443. --internet is reserved for base provisioning.
EOF
}

vm_dir=""
disk=""
display="gtk"
boot_cdrom=false
internet=false
worker_port=""
cdroms=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --vm-dir) vm_dir=${2:?missing --vm-dir value}; shift 2 ;;
        --disk) disk=${2:?missing --disk value}; shift 2 ;;
        --cdrom) cdroms+=("${2:?missing --cdrom value}"); shift 2 ;;
        --boot-cdrom) boot_cdrom=true; shift ;;
        --worker-port) worker_port=${2:?missing --worker-port value}; shift 2 ;;
        --internet) internet=true; shift ;;
        --display) display=${2:?missing --display value}; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) echo "unknown argument: $1" >&2; usage >&2; exit 64 ;;
    esac
done

if $internet && [[ -n "$worker_port" ]]; then
    echo "--internet and --worker-port cannot be combined" >&2
    exit 64
fi
if [[ -n "$worker_port" ]]; then
    [[ "$worker_port" =~ ^[0-9]+$ ]] || { echo "worker port is invalid" >&2; exit 65; }
    worker_port_number=$((10#$worker_port))
    if (( worker_port_number < 1024 || worker_port_number > 65535 )); then
        echo "worker port must be between 1024 and 65535" >&2
        exit 65
    fi
    worker_port=$worker_port_number
fi

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

if $internet; then
    netdev="user,id=net0"
else
    netdev="user,id=net0,restrict=on"
    if [[ -n "$worker_port" ]]; then
        netdev+=",hostfwd=tcp:127.0.0.1:${worker_port}-:8443"
    fi
fi

if $boot_cdrom; then
    disk_bootindex=2
else
    disk_bootindex=1
fi

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
    -device "ide-hd,drive=osdisk,bus=sata.0,bootindex=$disk_bootindex"
    -chardev "socket,id=chrtpm,path=$socket"
    -tpmdev emulator,id=tpm0,chardev=chrtpm
    -device tpm-crb,tpmdev=tpm0
    -netdev "$netdev"
    -device "e1000e,netdev=net0,mac=$mac"
    -device qemu-xhci
    -device usb-tablet
    -vga std
    -display "$display"
)

index=1
for iso in "${cdroms[@]}"; do
    iso=$(realpath "$iso")
    if $boot_cdrom && (( index == 1 )); then
        cdrom_bootindex=1
    else
        cdrom_bootindex=$((index + 1))
    fi
    arguments+=(
        -drive "if=none,id=cdrom$index,format=raw,media=cdrom,readonly=on,file=$iso"
        -device "ide-cd,drive=cdrom$index,bus=sata.$index,bootindex=$cdrom_bootindex"
    )
    index=$((index + 1))
done
arguments+=(-boot menu=on)

"$qemu" "${arguments[@]}"
