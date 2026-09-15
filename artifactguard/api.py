"""HTTP API for the local ArtifactGuard registry."""

from __future__ import annotations

import json
import os
import tempfile
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .registry import ArtifactRegistry

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
app = FastAPI(title="ArtifactGuard API", version="1.0.0")


@lru_cache(maxsize=1)
def registry() -> ArtifactRegistry:
    return ArtifactRegistry(os.getenv("ARTIFACTGUARD_ROOT", ".artifactguard"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "artifactguard"}


@app.get("/ready")
def ready() -> dict[str, str]:
    root = registry().root
    return {"status": "ready", "store": str(root)}


@app.post("/v1/artifacts")
async def upload_artifact(
    file: UploadFile = File(...),  # noqa: B008 - FastAPI uses the default as a request marker
    kind: str = Form("artifact"),
    metadata: str = Form("{}"),
) -> dict:
    try:
        parsed_metadata = json.loads(metadata)
        if not isinstance(parsed_metadata, dict):
            raise TypeError("metadata must be a JSON object")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="metadata must be valid JSON") from exc
    temporary_path: Path | None = None
    total = 0
    try:
        with tempfile.NamedTemporaryFile(prefix="artifactguard-", delete=False) as temporary:
            temporary_path = Path(temporary.name)
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="artifact exceeds 25 MiB limit")
                temporary.write(chunk)
        artifact = registry().ingest(temporary_path, kind=kind, metadata=parsed_metadata)
        return artifact.as_dict()
    finally:
        await file.close()
        if temporary_path:
            temporary_path.unlink(missing_ok=True)


@app.get("/v1/artifacts")
def list_artifacts(kind: str | None = None) -> list[dict]:
    return [item.as_dict() for item in registry().list(kind=kind)]


@app.get("/v1/artifacts/{artifact_digest}")
def artifact_metadata(artifact_digest: str) -> dict:
    artifact = registry().get(artifact_digest)
    if artifact is None:
        raise HTTPException(status_code=404, detail="artifact not found")
    return {**artifact.as_dict(), "integrity_ok": registry().verify(artifact_digest)}


@app.get("/v1/artifacts/{artifact_digest}/content")
def artifact_content(artifact_digest: str) -> FileResponse:
    try:
        path = registry().content_path(artifact_digest)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="artifact not found") from exc
    return FileResponse(path, media_type="application/octet-stream", filename=artifact_digest)
