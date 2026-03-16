from pathlib import Path

import boto3
from botocore.config import Config

from app.config import settings

LOCAL_STORAGE_ROOT = Path(__file__).resolve().parents[2] / "media"


def _use_s3() -> bool:
    return bool(settings.S3_BUCKET and settings.S3_ACCESS_KEY and settings.S3_SECRET_KEY)


def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT or None,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        config=Config(signature_version="s3v4"),
    )


def upload_file(file_bytes: bytes, key: str, content_type: str) -> str:
    if not _use_s3():
        destination = LOCAL_STORAGE_ROOT / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(file_bytes)
        return f"{settings.BACKEND_PUBLIC_URL}/media/{key}"

    client = _get_s3_client()
    client.put_object(
        Bucket=settings.S3_BUCKET,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
    )
    if settings.S3_ENDPOINT:
        return f"{settings.S3_ENDPOINT}/{settings.S3_BUCKET}/{key}"
    return f"https://{settings.S3_BUCKET}.s3.amazonaws.com/{key}"


def delete_file(key: str):
    if not _use_s3():
        destination = LOCAL_STORAGE_ROOT / key
        if destination.exists():
            destination.unlink()
        return

    client = _get_s3_client()
    client.delete_object(Bucket=settings.S3_BUCKET, Key=key)
