#!/usr/bin/env python3
"""Start a paused VM and eject its installer DVD on the first guest reset."""

from __future__ import annotations

import json
import pathlib
import socket
import sys
import time
from typing import Any

CONNECT_TIMEOUT_SECONDS = 30.0


class QMPError(RuntimeError):
    pass


class QMPClient:
    def __init__(self, path: pathlib.Path) -> None:
        deadline = time.monotonic() + CONNECT_TIMEOUT_SECONDS
        while True:
            try:
                self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.socket.connect(str(path))
                break
            except (FileNotFoundError, ConnectionRefusedError):
                self.socket.close()
                if time.monotonic() >= deadline:
                    raise QMPError(f"QMP socket did not become ready: {path}") from None
                time.sleep(0.05)
        self.stream = self.socket.makefile("rwb")
        greeting = self._read_message()
        if "QMP" not in greeting:
            raise QMPError("QEMU did not send a QMP greeting")

    def close(self) -> None:
        self.stream.close()
        self.socket.close()

    def _read_message(self) -> dict[str, Any]:
        line = self.stream.readline()
        if not line:
            raise EOFError("QMP connection closed")
        value = json.loads(line)
        if not isinstance(value, dict):
            raise QMPError("invalid QMP message")
        return value

    def execute(self, command: str, arguments: dict[str, Any] | None = None) -> None:
        request_id = command
        request: dict[str, Any] = {"execute": command, "id": request_id}
        if arguments is not None:
            request["arguments"] = arguments
        self.stream.write(json.dumps(request, separators=(",", ":")).encode() + b"\n")
        self.stream.flush()
        while True:
            response = self._read_message()
            if response.get("id") != request_id:
                continue
            if "error" in response:
                raise QMPError(f"QMP {command} failed: {response['error']}")
            return

    def wait_for_reset(self) -> None:
        while True:
            message = self._read_message()
            if message.get("event") == "RESET":
                return


def manage(path: pathlib.Path) -> None:
    client = QMPClient(path)
    try:
        client.execute("qmp_capabilities")
        client.execute("cont")
        client.wait_for_reset()
        client.execute(
            "blockdev-open-tray",
            {"device": "cdrom1", "force": True},
        )
    finally:
        client.close()


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {pathlib.Path(sys.argv[0]).name} QMP_SOCKET", file=sys.stderr)
        return 64
    try:
        manage(pathlib.Path(sys.argv[1]))
    except EOFError:
        # Closing the VM before its first reset is an ordinary failed/cancelled build.
        return 0
    except (OSError, QMPError, ValueError, json.JSONDecodeError) as error:
        print(f"installer boot management failed: {error}", file=sys.stderr)
        return 70
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
