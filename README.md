# ArtifactGuard

ArtifactGuard is a small content-addressed registry for datasets, model bundles, and evaluation reports. It creates portable SHA-256 manifests for directories, stores immutable blobs by digest, records searchable metadata in SQLite, and exposes the registry over a typed HTTP API.

The repository is deliberately self-contained. It uses only the Python standard library for hashing and storage plus FastAPI for the optional service, so a reviewer can inspect and run the complete integrity workflow locally.

## Start with the CLI

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,ops]'
python artifactguard.py manifest examples artifacts/examples.manifest.json
python artifactguard.py verify examples artifacts/examples.manifest.json
python artifactguard.py ingest examples/model-metadata.json --store .artifactguard --kind metadata --metadata '{"stage":"example"}'
python artifactguard.py list --store .artifactguard
python -m pytest tests -q
```

`manifest` records relative paths, byte counts, and SHA-256 values. `verify` fails closed when a tracked file changes or disappears. The manifest itself must live outside the directory being hashed.

## Run the registry service

```bash
uvicorn artifactguard.api:app --reload --port 8000
curl http://localhost:8000/ready
curl -F 'file=@examples/model-metadata.json' \
     -F 'kind=metadata' \
     -F 'metadata={"stage":"candidate"}' \
     http://localhost:8000/v1/artifacts
curl http://localhost:8000/v1/artifacts
```

The API provides `/health`, `/ready`, upload, listing, metadata, and content-download endpoints. Uploads are streamed to a temporary file and capped at 25 MiB. The object store uses atomic file replacement and the SQLite index is transactional, so retrying an identical upload is idempotent.

A non-root container is included:

```bash
docker build -t artifactguard .
docker run --rm -p 8000:8000 -v "$PWD/.artifactguard:/var/lib/artifactguard" artifactguard
```

## Technology and engineering choices

- Python 3.11+, SHA-256, SQLite, atomic filesystem writes
- FastAPI, multipart streaming, and typed health/readiness contracts
- Content-addressed storage with metadata filtering by artifact kind
- pytest, Ruff, GitHub Actions, and a non-root Docker image

The package API is intentionally small:

```python
from artifactguard import ArtifactRegistry

with ArtifactRegistry(".artifactguard") as registry:
    artifact = registry.ingest("model.joblib", kind="model", metadata={"run": "42"})
    assert registry.verify(artifact.digest)
```

## Scope and limitations

A checksum proves integrity relative to the registry or manifest; it does not prove authorship. This project does not provide authentication, authorization, encryption, or remote replication. Those controls belong around the service in a production deployment. Extra files in a manifest root are allowed so a pipeline can write temporary logs without invalidating an approved artifact set.
