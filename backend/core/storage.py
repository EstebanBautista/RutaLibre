"""Object storage for delivery photos (any S3-compatible service, via boto3).

In production the bucket lives on Backblaze B2; pointing the same code at AWS
S3 only takes different environment variables. The bucket is private: the
browser uploads with a short-lived presigned PUT and reads with a presigned
GET, and the server never handles the image bytes itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

UPLOAD_URL_TTL = 300  # seconds: the browser has 5 minutes to upload
VIEW_URL_TTL = 3600  # seconds: a photo link works for 1 hour
MAX_PHOTO_BYTES = 2 * 1024 * 1024
PHOTO_CONTENT_TYPE = "image/jpeg"

_REQUIRED = ("endpoint_url", "region", "bucket", "access_key_id", "secret_access_key")


class StorageError(Exception):
    """Any failure talking to the storage service (network, credentials, bucket)."""


@dataclass(frozen=True)
class ObjectInfo:
    size: int
    content_type: str


def is_configured() -> bool:
    """Photos are enabled only when every setting has a value."""
    config = settings.S3
    return all(config.get(name) for name in _REQUIRED)


@lru_cache(maxsize=4)
def _build_client(endpoint_url: str, region: str, access_key_id: str, secret_access_key: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url or None,  # empty means the default AWS endpoint (tests)
        region_name=region or None,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            # Newer boto3 adds a CRC32 checksum to presigned uploads. Backblaze
            # rejects it, so only add checksums where an operation requires them.
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
            retries={"max_attempts": 2},
            connect_timeout=5,
            read_timeout=10,
        ),
    )


def _client_cache_clear() -> None:
    _build_client.cache_clear()


def _client():
    config = settings.S3
    if not (config.get("bucket") and config.get("access_key_id") and config.get("secret_access_key")):
        raise StorageError("storage is not configured")
    return _build_client(
        config.get("endpoint_url", ""),
        config.get("region", ""),
        config["access_key_id"],
        config["secret_access_key"],
    )


# Tests reset the cached client when they change the settings.
_client.cache_clear = _client_cache_clear


def _bucket() -> str:
    return settings.S3["bucket"]


def presigned_put(key: str, content_type: str = PHOTO_CONTENT_TYPE, expires: int = UPLOAD_URL_TTL) -> str:
    """URL the browser uses to PUT the image straight into the bucket.

    The Content-Type is part of the signature, so the upload must send exactly it.
    """
    try:
        return _client().generate_presigned_url(
            "put_object",
            Params={"Bucket": _bucket(), "Key": key, "ContentType": content_type},
            ExpiresIn=expires,
        )
    except (BotoCoreError, ClientError) as exc:
        raise StorageError(str(exc)) from exc


def presigned_get(key: str, expires: int = VIEW_URL_TTL) -> str:
    """Temporary link to view a private object."""
    try:
        return _client().generate_presigned_url(
            "get_object", Params={"Bucket": _bucket(), "Key": key}, ExpiresIn=expires
        )
    except (BotoCoreError, ClientError) as exc:
        raise StorageError(str(exc)) from exc


def head(key: str) -> ObjectInfo | None:
    """Size and type of an object, or None when it does not exist."""
    client = _client()
    try:
        response = client.head_object(Bucket=_bucket(), Key=key)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") not in ("404", "NoSuchKey", "NotFound"):
            raise StorageError(str(exc)) from exc
        # A HEAD answer has no body, so "no such key" and "no such bucket" look
        # the same. Check the bucket to tell a missing photo from a broken setup.
        try:
            client.head_bucket(Bucket=_bucket())
        except (BotoCoreError, ClientError) as bucket_exc:
            raise StorageError(str(bucket_exc)) from bucket_exc
        return None
    except BotoCoreError as exc:
        raise StorageError(str(exc)) from exc
    return ObjectInfo(size=response["ContentLength"], content_type=response.get("ContentType", ""))


def delete(key: str) -> None:
    """Deletes an object. Deleting one that is already gone is not an error."""
    try:
        _client().delete_object(Bucket=_bucket(), Key=key)
    except (BotoCoreError, ClientError) as exc:
        raise StorageError(str(exc)) from exc


def delete_prefix(prefix: str) -> int:
    """Deletes every object whose key starts with prefix. Returns how many."""
    client = _client()
    deleted = 0
    try:
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=_bucket(), Prefix=prefix):
            keys = [{"Key": item["Key"]} for item in page.get("Contents", [])]
            if keys:
                client.delete_objects(Bucket=_bucket(), Delete={"Objects": keys, "Quiet": True})
                deleted += len(keys)
    except (BotoCoreError, ClientError) as exc:
        raise StorageError(str(exc)) from exc
    return deleted
