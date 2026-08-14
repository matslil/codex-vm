#!/usr/bin/env python3
"""Create a derived Windows ISO whose UEFI boot image skips the key prompt."""

from __future__ import annotations

import pathlib
import shutil
import struct
import subprocess
import sys

SECTOR_SIZE = 2048
DESCRIPTOR_START = 16
MAX_DESCRIPTORS = 64
EL_TORITO_ID = b"EL TORITO SPECIFICATION"
EFI_PLATFORM_ID = 0xEF
PROMPT_IMAGE = "efi/microsoft/boot/efisys.bin"
NOPROMPT_IMAGE = "efi/microsoft/boot/efisys_noprompt.bin"


class MediaError(ValueError):
    pass


def extract(seven_zip: str, iso: pathlib.Path, member: str) -> bytes:
    result = subprocess.run(
        [seven_zip, "x", "-so", str(iso), member],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip()
        raise MediaError(f"cannot extract {member}: {detail or '7z failed'}")
    if not result.stdout:
        raise MediaError(f"{member} is empty or missing")
    return result.stdout


def efi_boot_image_offset(iso: pathlib.Path) -> int:
    with iso.open("rb") as stream:
        catalog_lba: int | None = None
        for sector_number in range(DESCRIPTOR_START, DESCRIPTOR_START + MAX_DESCRIPTORS):
            stream.seek(sector_number * SECTOR_SIZE)
            descriptor = stream.read(SECTOR_SIZE)
            if len(descriptor) != SECTOR_SIZE:
                raise MediaError("the ISO is truncated")
            if descriptor[1:6] != b"CD001" or descriptor[6] != 1:
                raise MediaError("invalid ISO 9660 volume descriptors")
            if descriptor[0] == 0 and descriptor[7:39].rstrip(b" \0") == EL_TORITO_ID:
                catalog_lba = int.from_bytes(descriptor[71:75], "little")
            if descriptor[0] == 255:
                break
        if not catalog_lba:
            raise MediaError("no El Torito boot catalog was found")

        stream.seek(catalog_lba * SECTOR_SIZE)
        catalog = stream.read(32 * SECTOR_SIZE)
        validation = catalog[:32]
        if len(validation) != 32 or validation[0] != 1:
            raise MediaError("invalid El Torito validation entry")
        if validation[30:32] != b"\x55\xaa":
            raise MediaError("invalid El Torito validation signature")
        if sum(struct.unpack("<16H", validation)) & 0xFFFF:
            raise MediaError("invalid El Torito validation checksum")

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
                    raise MediaError("truncated El Torito boot entry")
                if header[1] == EFI_PLATFORM_ID and entry[0] == 0x88:
                    load_lba = int.from_bytes(entry[8:12], "little")
                    if not load_lba:
                        raise MediaError("invalid UEFI boot-image location")
                    return load_lba * SECTOR_SIZE
                offset += 32
            if header[0] == 0x91:
                break
    raise MediaError("no bootable UEFI entry was found")


def derive(source: pathlib.Path, destination: pathlib.Path, seven_zip: str) -> None:
    if destination.exists() or destination.is_symlink():
        raise MediaError(f"refusing to overwrite {destination}")
    prompt = extract(seven_zip, source, PROMPT_IMAGE)
    noprompt = extract(seven_zip, source, NOPROMPT_IMAGE)
    if len(prompt) != len(noprompt):
        raise MediaError("prompt and no-prompt UEFI boot images differ in size")
    if prompt == noprompt:
        raise MediaError("the supplied UEFI boot images are unexpectedly identical")

    image_offset = efi_boot_image_offset(source)
    with source.open("rb") as stream:
        stream.seek(image_offset)
        embedded = stream.read(len(prompt))
    if embedded != prompt:
        raise MediaError("the El Torito UEFI entry does not reference efisys.bin")

    try:
        subprocess.run(
            ["cp", "--reflink=auto", "--sparse=always", "--", str(source), str(destination)],
            check=True,
        )
        with destination.open("r+b") as stream:
            stream.seek(image_offset)
            stream.write(noprompt)
            stream.flush()
        shutil.copymode(source, destination)
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def main() -> int:
    if len(sys.argv) != 4:
        print(
            f"usage: {pathlib.Path(sys.argv[0]).name} SOURCE_ISO DESTINATION_ISO 7Z",
            file=sys.stderr,
        )
        return 64
    source, destination = map(pathlib.Path, sys.argv[1:3])
    try:
        derive(source.resolve(strict=True), destination, sys.argv[3])
    except (OSError, MediaError, subprocess.SubprocessError) as error:
        print(f"cannot create no-prompt Windows media: {error}", file=sys.stderr)
        return 65
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
