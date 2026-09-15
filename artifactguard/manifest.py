"""Portable SHA-256 manifests for directories of data and model artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def digest(path: str | Path) -> str:
    value = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def create(root: str | Path) -> dict[str, Any]:
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise ValueError("Root must be a directory")
    files = {}
    for path in sorted(root_path.rglob("*")):
        if not path.is_file() or path.is_symlink() or ".git" in path.parts:
            continue
        relative = str(path.relative_to(root_path))
        files[relative] = {"bytes": path.stat().st_size, "sha256": digest(path)}
    return {"schema_version": 1, "files": files}


def verify(root: str | Path, manifest: dict[str, Any]) -> list[str]:
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise ValueError("Root must be a directory")
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported manifest version")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise TypeError("Manifest files must be an object")
    failures = []
    for name, expected in files.items():
        path = (root_path / name).resolve()
        if not path.is_relative_to(root_path):
            raise ValueError("Manifest path escapes root")
        if not isinstance(expected, dict) or not path.is_file() or path.is_symlink():
            failures.append(name)
            continue
        if path.stat().st_size != expected.get("bytes") or digest(path) != expected.get("sha256"):
            failures.append(name)
    return failures
