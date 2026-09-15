import pytest

from artifactguard import ArtifactRegistry, create, verify


def test_tamper_detection_and_escape(tmp_path):
    file = tmp_path / "model.txt"
    file.write_text("v1")
    manifest = create(tmp_path)
    assert verify(tmp_path, manifest) == []
    file.write_text("v2")
    assert verify(tmp_path, manifest) == ["model.txt"]
    with pytest.raises(ValueError):
        verify(
            tmp_path,
            {"schema_version": 1, "files": {"../outside": {"bytes": 0, "sha256": "x"}}},
        )


def test_registry_deduplicates_and_detects_tampering(tmp_path):
    source = tmp_path / "model.bin"
    source.write_bytes(b"model-v1")
    store = tmp_path / "store"
    with ArtifactRegistry(store) as registry:
        first = registry.ingest(source, kind="model", metadata={"stage": "candidate"})
        second = registry.ingest(source, kind="model")
        assert first.digest == second.digest
        assert len(registry.list(kind="model")) == 1
        assert registry.verify(first.digest)
        registry.content_path(first.digest).write_bytes(b"tampered")
        assert not registry.verify(first.digest)
        assert (store / "registry.sqlite3").is_file()
