"""
Avatar image validation, sanitization, square cropping, and secure storage service.
Converts verified JPEG, PNG, and WebP inputs to clean, metadata-stripped 256x256 WebP files.
"""

import io
import os
import uuid
from pathlib import Path
from PIL import Image, ImageOps

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile

from accounts.models import UserProfile, AccountEvent
from accounts.services.activity_service import log_account_event

MAX_AVATAR_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_PIXELS = 10_000_000  # 10 Megapixels bomb guard
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
AVATAR_SIZE = (256, 256)


def get_avatars_dir() -> Path:
    """Returns absolute path to avatars storage directory, ensuring it exists."""
    avatars_dir = Path(settings.MEDIA_ROOT) / "avatars"
    avatars_dir.mkdir(parents=True, exist_ok=True)
    return avatars_dir


def delete_avatar_file(relative_path: str) -> None:
    """Safely removes an avatar file from the avatars directory."""
    if not relative_path:
        return
    clean_path = str(relative_path).lstrip("/\\").replace("\\", "/")
    full_path = (Path(settings.MEDIA_ROOT) / clean_path).resolve()
    media_root = Path(settings.MEDIA_ROOT).resolve()

    # Guard against directory traversal
    try:
        full_path.relative_to(media_root)
    except ValueError:
        return

    if full_path.is_file():
        try:
            full_path.unlink()
        except OSError:
            pass


def process_and_save_avatar(user, uploaded_file: UploadedFile, request=None) -> str:
    """
    Validates, sanitizes, square-crops, resizes to 256x256, and stores an avatar image as WebP.
    Rejects files over 2 MB, non-images, decompression bombs, and animated/multi-frame files.
    Replaces and deletes previous avatar file if present.
    Returns the relative path under MEDIA_ROOT (e.g. 'avatars/<uuid>.webp').
    """
    if not uploaded_file:
        raise ValidationError("No file was uploaded.")

    # 1. Size guard: Max 2 MB
    if uploaded_file.size > MAX_AVATAR_BYTES:
        raise ValidationError("Avatar file size must not exceed 2 MB.")

    file_bytes = uploaded_file.read()
    if len(file_bytes) > MAX_AVATAR_BYTES:
        raise ValidationError("Avatar file size must not exceed 2 MB.")

    # 2. Inspect with Pillow
    try:
        # Enforce decompression bomb safety
        Image.MAX_IMAGE_PIXELS = MAX_PIXELS
        img_buffer = io.BytesIO(file_bytes)
        with Image.open(img_buffer) as img:
            real_format = img.format
            if not real_format or real_format.upper() not in ALLOWED_FORMATS:
                raise ValidationError("Only JPEG, PNG, and WebP images are supported.")

            # Decompression bomb dimension guard
            width, height = img.size
            if width * height > MAX_PIXELS:
                raise ValidationError("Image dimensions are excessively large.")

            # Reject animated or multi-frame files
            is_animated = getattr(img, "is_animated", False)
            n_frames = getattr(img, "n_frames", 1)
            if is_animated or n_frames > 1:
                raise ValidationError("Animated and multi-frame images are not permitted.")

            # Apply EXIF transpose to honor orientation before stripping metadata
            img = ImageOps.exif_transpose(img)

            # Center crop to a square
            w, h = img.size
            min_dim = min(w, h)
            left = (w - min_dim) // 2
            top = (h - min_dim) // 2
            right = left + min_dim
            bottom = top + min_dim
            cropped = img.crop((left, top, right, bottom))

            # Resize to 256x256
            resized = cropped.resize(AVATAR_SIZE, Image.Resampling.LANCZOS)

            # Handle color modes cleanly for WebP
            if resized.mode in ("RGBA", "LA") or (resized.mode == "P" and "transparency" in resized.info):
                final_img = resized.convert("RGBA")
            else:
                final_img = resized.convert("RGB")

            # Re-encode to WebP without any metadata/EXIF
            output_buffer = io.BytesIO()
            final_img.save(output_buffer, format="WEBP", quality=85, method=6)
            webp_bytes = output_buffer.getvalue()

    except Image.DecompressionBombError:
        raise ValidationError("Image exceeds decompression safety limits.")
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(f"Invalid or corrupted image file: {exc}")

    # 3. Store file under MEDIA_ROOT/avatars/<uuid>.webp
    avatars_dir = get_avatars_dir()
    new_filename = f"{uuid.uuid4().hex}.webp"
    full_path = avatars_dir / new_filename
    with open(full_path, "wb") as f:
        f.write(webp_bytes)

    relative_path = f"avatars/{new_filename}"

    # 4. Clean up previous avatar if present
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if profile.avatar_path:
        delete_avatar_file(profile.avatar_path)

    profile.avatar_path = relative_path
    profile.save(update_fields=["avatar_path", "updated_at"])

    # 5. Log AccountEvent
    log_account_event(
        user,
        AccountEvent.EventType.AVATAR_UPDATED,
        request=request,
        metadata={"avatar_path": relative_path},
    )

    return relative_path


def remove_avatar(user, request=None) -> None:
    """
    Removes user's avatar, deletes file from disk, and resets avatar_path.
    """
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if profile.avatar_path:
        delete_avatar_file(profile.avatar_path)
        profile.avatar_path = ""
        profile.save(update_fields=["avatar_path", "updated_at"])

        log_account_event(
            user,
            AccountEvent.EventType.AVATAR_REMOVED,
            request=request,
        )
