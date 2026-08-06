#!/bin/sh
set -eu

python3 -m venv /opt/codex-vm
/opt/codex-vm/bin/python -m pip install --no-index /tmp/codex_vm-*.whl
install -d -m 0700 /var/lib/codex-vm /run/codex-vm
install -m 0644 /tmp/codex-vm.service /etc/systemd/system/codex-vm.service
systemctl daemon-reload
systemctl enable codex-vm.service

