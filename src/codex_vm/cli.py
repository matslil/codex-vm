"""Command-line entry points for worker and controller operations."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path

from .api import serve
from .controller import WorkerClient, git_archive
from .manager import JobManager
from .runtime import DockerRuntime, EnvironmentRuntime, NativeRuntime
from .security import safe_name
from .store import JobStore


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="codex-vm")
    commands = result.add_subparsers(dest="command", required=True)

    worker = commands.add_parser("serve", help="run the disposable VM worker API")
    worker.add_argument("--host", default="127.0.0.1")
    worker.add_argument("--port", type=int, default=8443)
    worker.add_argument("--root", type=Path, default=Path("work"))
    worker.add_argument("--max-input-mib", type=int, default=4096)
    worker.add_argument("--certificate", type=Path)
    worker.add_argument("--private-key", type=Path)
    worker.add_argument("--client-ca", type=Path)
    worker.add_argument("--runtime", choices=("auto", "docker", "native"), default="auto")
    worker.add_argument(
        "--environment-manifest",
        type=Path,
        default=Path(r"C:\ProgramData\codex-vm\environment.json"),
    )

    archive = commands.add_parser("archive", help="create a source archive from local Git")
    archive.add_argument("repository", type=Path)
    archive.add_argument("output", type=Path)
    archive.add_argument("--revision", default="HEAD")
    archive.add_argument("--prefix", default="source/")

    health = commands.add_parser("health", help="query a worker")
    health.add_argument("url")
    _tls_arguments(health)

    submit = commands.add_parser("submit", help="submit and wait for one worker job")
    submit.add_argument("url")
    submit.add_argument("spec", type=Path)
    submit.add_argument("--input", action="append", default=[], metavar="NAME=PATH")
    submit.add_argument("--results", type=Path, default=Path("results"))
    _tls_arguments(submit)
    return result


def _tls_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument("--ca", type=Path)
    command.add_argument("--certificate", type=Path)
    command.add_argument("--private-key", type=Path)


def main(arguments: Sequence[str] | None = None) -> int:
    args = parser().parse_args(arguments)
    if args.command == "serve":
        manager = JobManager(
            JobStore(args.root),
            _worker_runtime(args.runtime, args.environment_manifest),
            maximum_input_bytes=args.max_input_mib * 1024 * 1024,
        )
        serve(
            manager,
            args.host,
            args.port,
            certificate=args.certificate,
            private_key=args.private_key,
            client_ca=args.client_ca,
        )
        return 0
    if args.command == "archive":
        manifest = git_archive(args.repository, args.revision, args.output, args.prefix)
        print(json.dumps(manifest, indent=2))
        return 0
    client = WorkerClient(
        args.url,
        ca=args.ca,
        certificate=args.certificate,
        private_key=args.private_key,
    )
    if args.command == "health":
        print(json.dumps(client.health(), indent=2))
        return 0
    if args.command == "submit":
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        inputs: dict[str, Path] = {}
        for assignment in args.input:
            name, separator, path = assignment.partition("=")
            if not separator:
                raise SystemExit(f"invalid --input value: {assignment}")
            inputs[name] = Path(path)
        client.submit(spec, inputs)
        state = client.wait(str(spec["job_id"]))
        args.results.mkdir(parents=True, exist_ok=True)
        for artifact in state.get("artifacts", []):
            filename = safe_name(str(artifact["filename"]))
            client.download(str(spec["job_id"]), artifact, args.results / filename)
        print(json.dumps(state, indent=2))
        return 0 if state["state"] == "succeeded" else 1
    raise AssertionError(args.command)


def _worker_runtime(kind: str, manifest: Path) -> EnvironmentRuntime:
    if kind == "auto":
        kind = "native" if os.name == "nt" else "docker"
    if kind == "native":
        return NativeRuntime(manifest)
    return DockerRuntime()


if __name__ == "__main__":
    raise SystemExit(main())
