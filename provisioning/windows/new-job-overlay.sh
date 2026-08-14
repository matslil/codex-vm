#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
    echo "usage: $0 ENVIRONMENT.qcow2 JOB.qcow2" >&2
    exit 64
fi

parent=$(realpath "$1")
output=$2

if [ ! -f "$parent" ]; then
    echo "environment image does not exist: $parent" >&2
    exit 66
fi
if [ -e "$output" ]; then
    echo "refusing to overwrite job disk: $output" >&2
    exit 73
fi

qemu-img create -f qcow2 -F qcow2 -b "$parent" "$output"
qemu-img info --output=json "$output"
