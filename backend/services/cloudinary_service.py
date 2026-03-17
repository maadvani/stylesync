"""
Upload wardrobe images to Cloudinary; return public URL.
You set up Cloudinary once (free account) and add credentials to .env.
"""
import io
from config import Settings
import cloudinary
import cloudinary.uploader


def configure():
    # Re-read env on each call so changes to backend/.env apply after restart,
    # and are not coupled to module import order.
    settings = Settings()
    if not settings.cloudinary_cloud_name or not settings.cloudinary_api_key:
        return False
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
    )
    return True


def upload_image(
    file_bytes: bytes,
    content_type: str,
    folder: str = "stylesync/wardrobe",
) -> tuple[str | None, str | None]:
    """
    Upload image bytes to Cloudinary.
    Returns (public_url, error_message). On success, error_message is None.
    """
    if not configure():
        return None, "Cloudinary is not configured (missing CLOUDINARY_* env vars)."
    try:
        # Cloudinary accepts file-like object
        stream = io.BytesIO(file_bytes)
        r = cloudinary.uploader.upload(
            stream,
            folder=folder,
            resource_type="image",
        )
        return r.get("secure_url"), None
    except Exception as e:
        return None, f"Cloudinary upload error: {e}"
