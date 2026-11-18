"""Private document storage with a Neon S3-compatible backend and a secure local fallback."""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path, PurePosixPath

from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from .config import settings


class StorageError(RuntimeError):
    """Storage is unavailable or rejected an operation."""


class StorageNotFound(StorageError):
    """The requested private object does not exist."""


def object_storage_configured() -> bool:
    values = (
        settings.aws_endpoint_url_s3,
        settings.aws_region,
        settings.aws_access_key_id,
        settings.aws_secret_access_key,
        settings.document_storage_bucket,
    )
    return all(values)


def _validate_key(storage_key: str) -> str:
    if not isinstance(storage_key, str) or not storage_key or len(storage_key) > 1024:
        raise StorageError("Invalid document storage key")
    if "\\" in storage_key or storage_key.startswith("/"):
        raise StorageError("Invalid document storage key")
    parts = storage_key.split("/")
    if len(parts) < 3 or any(part in {"", ".", ".."} for part in parts):
        raise StorageError("Invalid document storage key")
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", parts[0]) or not re.fullmatch(r"[0-9a-fA-F-]{36}", parts[1]):
        raise StorageError("Invalid document storage key")
    return str(PurePosixPath(*parts))


def _local_path(storage_key: str) -> Path:
    key = _validate_key(storage_key)
    root = Path(settings.document_storage_path).resolve()
    target = (root / key).resolve()
    if not target.is_relative_to(root):
        raise StorageError("Invalid document storage path")
    return target


@lru_cache(maxsize=1)
def _s3_client():
    if not object_storage_configured():
        return None
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=settings.aws_endpoint_url_s3,
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def store_private_file(
    org_id: str, document_id: str, version: int, data: bytes, suffix: str, content_type: str | None = None
) -> str:
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", org_id) or not re.fullmatch(r"[0-9a-fA-F-]{36}", document_id):
        raise StorageError("Invalid tenant or document identifier")
    safe_suffix = suffix.lower() if re.fullmatch(r"\.[a-z0-9]{1,10}", suffix or "") else ""
    key = f"{org_id}/{document_id}/v{version}-{os.urandom(16).hex()}{safe_suffix}"
    client = _s3_client()
    if client is not None:
        try:
            client.put_object(
                Bucket=settings.document_storage_bucket,
                Key=key,
                Body=data,
                ContentType=content_type or "application/octet-stream",
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageError("Private object upload failed") from exc
        return key

    path = _local_path(key)
    root = Path(settings.document_storage_path).resolve()
    org_dir = root / org_id
    document_dir = org_dir / document_id
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    org_dir.mkdir(mode=0o700, exist_ok=True)
    document_dir.mkdir(mode=0o700, exist_ok=True)
    os.chmod(root, 0o700)
    os.chmod(org_dir, 0o700)
    os.chmod(document_dir, 0o700)
    temp = path.with_suffix(path.suffix + ".tmp")
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        os.chmod(path, 0o600)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
    return key


def read_private_file(storage_key: str) -> bytes:
    key = _validate_key(storage_key)
    client = _s3_client()
    if client is not None:
        try:
            response = client.get_object(Bucket=settings.document_storage_bucket, Key=key)
            body = response["Body"]
            try:
                return body.read()
            finally:
                body.close()
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"NoSuchKey", "NotFound", "404"}:
                raise StorageNotFound("Private document not found") from exc
            raise StorageError("Private object download failed") from exc
        except BotoCoreError as exc:
            raise StorageError("Private object download failed") from exc

    path = _local_path(key)
    try:
        return path.read_bytes()
    except FileNotFoundError as exc:
        raise StorageNotFound("Private document not found") from exc
    except OSError as exc:
        raise StorageError("Private document read failed") from exc


def delete_private_file(storage_key: str) -> None:
    key = _validate_key(storage_key)
    client = _s3_client()
    if client is not None:
        try:
            client.delete_object(Bucket=settings.document_storage_bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise StorageError("Private object deletion failed") from exc
        return
    try:
        _local_path(key).unlink(missing_ok=True)
    except OSError as exc:
        raise StorageError("Private document deletion failed") from exc
