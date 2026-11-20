from io import BytesIO
from uuid import uuid4

import pytest

from app import document_storage as storage


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.last_put = None

    def put_object(self, **kwargs):
        self.last_put = kwargs
        self.objects[kwargs["Key"]] = kwargs["Body"]

    def get_object(self, **kwargs):
        return {"Body": BytesIO(self.objects[kwargs["Key"]])}

    def delete_object(self, **kwargs):
        self.objects.pop(kwargs["Key"], None)


def test_local_private_storage_roundtrip_and_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "_s3_client", lambda: None)
    monkeypatch.setattr(storage.settings, "document_storage_path", str(tmp_path))
    key = storage.store_private_file(str(uuid4()), str(uuid4()), 1, b"private document", ".pdf", "application/pdf")
    assert storage.read_private_file(key) == b"private document"
    storage.delete_private_file(key)
    with pytest.raises(storage.StorageNotFound):
        storage.read_private_file(key)


def test_neon_s3_private_storage_roundtrip(monkeypatch):
    client = FakeS3()
    monkeypatch.setattr(storage, "_s3_client", lambda: client)
    monkeypatch.setattr(storage.settings, "document_storage_bucket", "cfdt-juris-documents")
    key = storage.store_private_file(str(uuid4()), str(uuid4()), 2, b"private s3 document", ".pdf", "application/pdf")
    assert client.last_put["Bucket"] == "cfdt-juris-documents"
    assert client.last_put["ContentType"] == "application/pdf"
    assert storage.read_private_file(key) == b"private s3 document"
    storage.delete_private_file(key)
    assert key not in client.objects


def test_private_storage_rejects_path_traversal():
    with pytest.raises(storage.StorageError):
        storage.read_private_file("../../secrets.txt")
