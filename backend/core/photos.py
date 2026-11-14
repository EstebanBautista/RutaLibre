"""Rules for the evidence photo of a route stop.

Uploading takes two steps so the image never passes through this server:

1. request_upload(): we sign a short-lived URL for a brand-new key in a
   temporary area (uploads/). The exact size is part of the signature, so the
   bucket refuses anything bigger than what the client declared (≤ 2 MB).
2. The browser PUTs the image straight to that temporary key.
3. confirm_upload(): we check the object exists, is a small JPEG and belongs
   to this stop, then copy it inside the bucket to its final key
   (businesses/...) and delete the temporary one. The browser never gets a
   URL for the final key, so a confirmed photo cannot be overwritten.

Anything left behind in uploads/ (an upload never confirmed, or a second PUT
after confirming) is removed by the bucket's lifecycle rule after one day.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from core import storage
from core.exceptions import BadRequest, PhotosDisabled, StorageDown, TooManyUploads
from core.models import RouteStop, UploadGrant
from core.storage import StorageError

logger = logging.getLogger(__name__)

# Per business. At most 200 × 2 MB = 400 MB of uploads a day.
MAX_UPLOADS_PER_MINUTE = 30
MAX_UPLOADS_PER_DAY = 200

UPLOADS_ROOT = "uploads/"
PHOTOS_ROOT = "businesses/"

# The part of a key after the stop's path: 32 hex characters and ".jpg".
_KEY_NAME = re.compile(r"^[0-9a-f]{32}\.jpg$")


def _stop_path(stop: RouteStop) -> str:
    return f"{stop.route.business_id}/routes/{stop.route_id}/stops/{stop.pk}/"


def upload_prefix(stop: RouteStop) -> str:
    """Temporary area the browser uploads to."""
    return f"{UPLOADS_ROOT}{_stop_path(stop)}"


def key_prefix(stop: RouteStop) -> str:
    """Where the stop's confirmed photo lives."""
    return f"{PHOTOS_ROOT}{_stop_path(stop)}"


def business_prefixes(business_id: int) -> list[str]:
    """Every place in the bucket that holds objects of a business."""
    return [f"{PHOTOS_ROOT}{business_id}/", f"{UPLOADS_ROOT}{business_id}/"]


def _require_enabled() -> None:
    if not storage.is_configured():
        raise PhotosDisabled()


def _check_limits(business_id: int) -> None:
    now = timezone.now()
    recent = UploadGrant.objects.filter(business_id=business_id)
    if recent.filter(created_at__gte=now - timedelta(minutes=1)).count() >= MAX_UPLOADS_PER_MINUTE:
        raise TooManyUploads()
    if recent.filter(created_at__gte=now - timedelta(days=1)).count() >= MAX_UPLOADS_PER_DAY:
        raise TooManyUploads()


def request_upload(stop: RouteStop, size: object) -> dict:
    """Returns {"upload_url", "key", "headers"} for the browser to PUT the image.

    size is the number of bytes the browser will send; it is signed into the URL.
    """
    _require_enabled()
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise BadRequest("Falta el tamaño de la foto.")
    if size > storage.MAX_PHOTO_BYTES:
        raise BadRequest("La foto supera 2 MB.")
    _check_limits(stop.route.business_id)

    key = f"{upload_prefix(stop)}{uuid.uuid4().hex}.jpg"
    try:
        url = storage.presigned_put(key, size=size)
    except StorageError:
        raise StorageDown() from None
    UploadGrant.objects.create(business_id=stop.route.business_id)
    return {"upload_url": url, "key": key, "headers": {"Content-Type": storage.PHOTO_CONTENT_TYPE}}


def confirm_upload(stop: RouteStop, key: str) -> None:
    """Validates the uploaded object and makes it the stop's photo."""
    _require_enabled()
    prefix = upload_prefix(stop)
    name = key[len(prefix):] if key.startswith(prefix) else ""
    if not _KEY_NAME.match(name):
        raise BadRequest("La foto no corresponde a esta parada.")
    final_key = f"{key_prefix(stop)}{name}"

    old_key = ""
    try:
        with transaction.atomic():
            locked = RouteStop.objects.select_for_update().get(pk=stop.pk)
            if locked.photo_key == final_key:
                return  # already confirmed (double click): nothing to do

            info = storage.head(key)
            if info is None:
                raise BadRequest("No se encontró la foto subida. Vuelve a intentarlo.")
            if info.size > storage.MAX_PHOTO_BYTES:
                storage.delete(key)
                raise BadRequest("La foto supera 2 MB.")
            if info.content_type != storage.PHOTO_CONTENT_TYPE:
                storage.delete(key)
                raise BadRequest("La foto debe ser JPEG.")

            storage.copy(key, final_key)
            old_key = locked.photo_key
            locked.photo_key = final_key
            locked.photo_uploaded_at = timezone.now()
            locked.save(update_fields=["photo_key", "photo_uploaded_at"])
    except StorageError:
        raise StorageDown() from None

    # Cleanup after the new photo is saved: a failure here must not lose it.
    for leftover in (key, old_key if old_key != final_key else ""):
        if not leftover:
            continue
        try:
            storage.delete(leftover)
        except StorageError:
            logger.warning("Could not delete %s", leftover)


def view_url(stop: RouteStop) -> str | None:
    """Temporary link to see the stop's photo, or None when there is nothing to show."""
    if not stop.photo_key or not storage.is_configured():
        return None
    try:
        return storage.presigned_get(stop.photo_key)
    except StorageError:
        logger.warning("Could not sign a view URL for %s", stop.photo_key)
        return None
