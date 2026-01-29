"""S3 upload helper for profile photos and other assets."""

import uuid
import logging
from typing import Optional

from app.core.config import settings
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)

# Max size for profile photo (5 MB)
PROFILE_PHOTO_MAX_BYTES = 5 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}
EXT_BY_CONTENT_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _get_s3_client():
    """Create S3 client. Raises if S3 is not configured."""
    if not settings.S3_BUCKET_NAME:
        AppException().raise_400(
            "Profile photo upload is not configured. Set S3_BUCKET_NAME and AWS credentials."
        )
    try:
        import boto3
        from botocore.config import Config
        config = Config(signature_version="s3v4", region_name=settings.AWS_REGION)
        kwargs = {"region_name": settings.AWS_REGION, "config": config}
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
            kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
        return boto3.client("s3", **kwargs)
    except Exception as e:
        logger.exception("Failed to create S3 client: %s", e)
        AppException().raise_500("Storage is temporarily unavailable.")


def upload_customer_profile_photo(
    file_content: bytes,
    customer_id: str,
    content_type: str,
    original_filename: Optional[str] = None,
) -> str:
    """
    Upload customer profile photo to S3. Returns the public URL of the object.

    Args:
        file_content: Raw file bytes.
        customer_id: Customer UUID string.
        content_type: MIME type (e.g. image/jpeg).
        original_filename: Optional original filename (used only for extension hint).

    Returns:
        Public URL of the uploaded object (https://bucket.s3.region.amazonaws.com/key).
    """
    if len(file_content) > PROFILE_PHOTO_MAX_BYTES:
        AppException().raise_400(
            f"File too large. Maximum size is {PROFILE_PHOTO_MAX_BYTES // (1024 * 1024)} MB."
        )
    if content_type not in ALLOWED_CONTENT_TYPES:
        AppException().raise_400(
            f"Invalid file type. Allowed: {', '.join(ALLOWED_CONTENT_TYPES)}"
        )
    ext = EXT_BY_CONTENT_TYPE.get(content_type, ".jpg")
    key = f"{settings.S3_CUSTOMER_PROFILE_PREFIX}/{customer_id}/{uuid.uuid4().hex}{ext}"
    client = _get_s3_client()
    bucket = settings.S3_BUCKET_NAME
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=file_content,
            ContentType=content_type,
            CacheControl="max-age=31536000",
        )
    except Exception as e:
        logger.exception("S3 upload failed: %s", e)
        AppException().raise_500("Failed to upload photo. Please try again.")
    # Public URL (bucket must allow public read for this prefix, or use CloudFront)
    url = f"https://{bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
    return url
