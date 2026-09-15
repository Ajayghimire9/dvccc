"""A small content-addressed artifact registry backed by SQLite."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

from .manifest import digest


@dataclass(frozen=True)
class Artifact:
    digest: str
    kind: str
    bytes: int
    path: str
    metadata: dict[str, Any]
    created_at: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ArtifactRegistry:
    """Store immutable blobs by digest and index them with queryable metadata."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.objects = self.root / "objects"
        self.objects.mkdir(parents=True, exist_ok=True)
        self.database = self.root / "registry.sqlite3"
        self.connection = sqlite3.connect(self.database)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS artifacts (
                digest TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                bytes INTEGER NOT NULL,
                path TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _row(self, row: sqlite3.Row | None) -> Artifact | None:
        if row is None:
            return None
        return Artifact(
            digest=row["digest"],
            kind=row["kind"],
            bytes=row["bytes"],
            path=row["path"],
            metadata=json.loads(row["metadata_json"]),
            created_at=row["created_at"],
        )

    def ingest(
        self,
        source: str | Path,
        *,
        kind: str = "artifact",
        metadata: dict[str, Any] | None = None,
    ) -> Artifact:
        source_path = Path(source)
        if not source_path.is_file():
            raise FileNotFoundError(f"Artifact does not exist: {source_path}")
        artifact_digest = digest(source_path)
        size = source_path.stat().st_size
        object_path = self.objects / artifact_digest
        if not object_path.exists():
            with tempfile.NamedTemporaryFile(dir=self.objects, prefix=".upload-", delete=False) as temp:
                temporary = Path(temp.name)
                with source_path.open("rb") as source_handle:
                    shutil.copyfileobj(source_handle, temp, length=1024 * 1024)
                temp.flush()
                os.fsync(temp.fileno())
            os.replace(temporary, object_path)
        created_at = datetime.now(UTC).isoformat()
        payload = json.dumps(metadata or {}, sort_keys=True, separators=(",", ":"))
        self.connection.execute(
            "INSERT OR IGNORE INTO artifacts(digest, kind, bytes, path, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (artifact_digest, kind, size, str(object_path.relative_to(self.root)), payload, created_at),
        )
        self.connection.commit()
        result = self.get(artifact_digest)
        if result is None:  # pragma: no cover - defensive database guard
            raise RuntimeError("Artifact registry failed to persist the artifact")
        return result

    def get(self, artifact_digest: str) -> Artifact | None:
        row = self.connection.execute(
            "SELECT digest, kind, bytes, path, metadata_json, created_at FROM artifacts WHERE digest = ?",
            (artifact_digest,),
        ).fetchone()
        return self._row(row)

    def list(self, *, kind: str | None = None) -> list[Artifact]:
        if kind:
            rows = self.connection.execute(
                "SELECT digest, kind, bytes, path, metadata_json, created_at FROM artifacts WHERE kind = ? ORDER BY created_at DESC",
                (kind,),
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT digest, kind, bytes, path, metadata_json, created_at FROM artifacts ORDER BY created_at DESC"
            ).fetchall()
        return [self._row(row) for row in rows if row is not None]

    def verify(self, artifact_digest: str) -> bool:
        artifact = self.get(artifact_digest)
        if artifact is None:
            raise KeyError(artifact_digest)
        object_path = self.root / artifact.path
        return object_path.is_file() and object_path.stat().st_size == artifact.bytes and digest(object_path) == artifact.digest

    def content_path(self, artifact_digest: str) -> Path:
        artifact = self.get(artifact_digest)
        if artifact is None:
            raise KeyError(artifact_digest)
        path = (self.root / artifact.path).resolve()
        if not path.is_relative_to(self.objects.resolve()):
            raise ValueError("Registry path escapes object store")
        return path
