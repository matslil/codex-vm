#!/usr/bin/env python3
"""Reject files that are not UEFI-bootable ISO 9660 installation media."""

from __future__ import annotations

import pathlib
import struct
import sys
from typing import BinaryIO

SECTOR_SIZE = 2048
DESCRIPTOR_START = 16
MAX_DESCRIPTORS = 64
EL_TORITO_ID = b"EL TORITO SPECIFICATION"
EFI_PLATFORM_ID = 0xEF


class InvalidMedia(ValueError):
    pass


def read_exact(stream: BinaryIO, offset: int, size: int) -> bytes:
    stream.seek(offset)
    value = stream.read(size)
    if len(value) != size:
        raise InvalidMedia("the file is truncated")
    return value


def has_bootable_efi_entry(catalog: bytes) -> bool:
    validation = catalog[:32]
    if len(validation) != 32 or validation[0] != 0x01:
        return False
    if validation[30:32] != b"\x55\xaa":
        return False
    if sum(struct.unpack("<16H", validation)) & 0xFFFF:
        return False

    default_entry = catalog[32:64]
    if validation[1] == EFI_PLATFORM_ID and default_entry[:1] == b"\x88":
        return True

    offset = 64
    while offset + 32 <= len(catalog):
        header = catalog[offset : offset + 32]
        if header[0] not in (0x90, 0x91):
            break
        entry_count = int.from_bytes(header[2:4], "little")
        offset += 32
        for _ in range(entry_count):
            entry = catalog[offset : offset + 32]
            if len(entry) != 32:
                return False
            if header[1] == EFI_PLATFORM_ID and entry[0] == 0x88:
                return True
            offset += 32
        if header[0] == 0x91:
            break
    return False


def validate(path: pathlib.Path) -> None:
    with path.open("rb") as stream:
        primary_found = False
        catalog_lba: int | None = None
        for sector_number in range(DESCRIPTOR_START, DESCRIPTOR_START + MAX_DESCRIPTORS):
            descriptor = read_exact(stream, sector_number * SECTOR_SIZE, SECTOR_SIZE)
            if descriptor[1:6] != b"CD001" or descriptor[6] != 1:
                raise InvalidMedia("the ISO 9660 volume descriptors are invalid")
            descriptor_type = descriptor[0]
            if descriptor_type == 0:
                system_id = descriptor[7:39].rstrip(b" \0")
                if system_id == EL_TORITO_ID:
                    catalog_lba = int.from_bytes(descriptor[71:75], "little")
            elif descriptor_type == 1:
                primary_found = True
            elif descriptor_type == 255:
                break

        if not primary_found:
            raise InvalidMedia("no ISO 9660 primary volume descriptor was found")
        if not catalog_lba:
            raise InvalidMedia("no El Torito boot catalog was found")

        stream.seek(catalog_lba * SECTOR_SIZE)
        catalog = stream.read(32 * SECTOR_SIZE)
        if not has_bootable_efi_entry(catalog):
            raise InvalidMedia("the El Torito catalog has no bootable UEFI entry")


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {pathlib.Path(sys.argv[0]).name} WINDOWS_ISO", file=sys.stderr)
        return 64
    path = pathlib.Path(sys.argv[1])
    try:
        validate(path)
    except (OSError, InvalidMedia) as error:
        print(f"invalid Windows installation media: {path}: {error}", file=sys.stderr)
        return 65
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
