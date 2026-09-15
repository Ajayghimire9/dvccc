"""Command-line interface for ArtifactGuard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .manifest import create, verify
from .registry import ArtifactRegistry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    manifest = commands.add_parser("manifest", help="create a directory manifest")
    manifest.add_argument("root")
    manifest.add_argument("output")

    check = commands.add_parser("verify", help="verify a directory manifest")
    check.add_argument("root")
    check.add_argument("manifest")

    ingest = commands.add_parser("ingest", help="store an immutable artifact")
    ingest.add_argument("source")
    ingest.add_argument("--store", default=".artifactguard")
    ingest.add_argument("--kind", default="artifact")
    ingest.add_argument("--metadata", default="{}", help="JSON object")

    listing = commands.add_parser("list", help="list registry artifacts")
    listing.add_argument("--store", default=".artifactguard")
    listing.add_argument("--kind")
    args = parser.parse_args()

    if args.command == "manifest":
        output = Path(args.output)
        if output.resolve().is_relative_to(Path(args.root).resolve()):
            parser.error("Store the manifest outside the hashed directory")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(create(args.root), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return
    if args.command == "verify":
        failures = verify(args.root, json.loads(Path(args.manifest).read_text(encoding="utf-8")))
        print(json.dumps({"valid": not failures, "changed_or_missing": failures}))
        raise SystemExit(1 if failures else 0)
    with ArtifactRegistry(args.store) as registry:
        if args.command == "ingest":
            artifact = registry.ingest(args.source, kind=args.kind, metadata=json.loads(args.metadata))
            print(json.dumps(artifact.as_dict(), indent=2, sort_keys=True))
        else:
            print(json.dumps([item.as_dict() for item in registry.list(kind=args.kind)], indent=2, sort_keys=True))
