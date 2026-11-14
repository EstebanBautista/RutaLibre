"""Rules for the evidence photo of a route stop.

Uploading takes two steps so the image never passes through this server:

1. request_upload(): we sign a short-lived URL for a brand-new key that we
   choose, so the client cannot pick where its file lands.
2. The browser PUTs the image straight to the bucket.
3. confirm_upload(): we check the object really exists, is a small JPEG and
   belongs to this stop, and only then record its key on the stop.
"""

from __future__ import annotations

import logging
import re
import uuid

from django.db import transaction
from django.utils import timezone

from core import storage
from core.exceptions import BadRequest, PhotosDisabled, StorageDown
from core.models import RouteStop
from core.storage import StorageError

logger = logging.getLogger(__name__)

# The part of a key after the stop's prefix: 32 hex characters and ".jpg".
_KEY_NAME = re.compile(r"^[0-9a-f]{32}\.jpg$")


def key_prefix(stop: RouteStop) -> str:
    return f"businesses/{stop.route.business_id}/routes/{stop.route_id}/stops/{stop.pk}/"


def new_key(stop: RouteStop) -> str:
    return f"{key_prefix(stop)}{uuid.uuid4().hex}.jpg"


def _require_enabled() -> None:
    if not storage.is_configured():
        raise PhotosDisabled()


def request_upload(stop: RouteStop) -> dict:
    """Returns {"upload_url", "key", "headers"} for the browser to PUT the image."""
    _require_enabled()
    key = new_key(stop)
    try:
        url = storage.presigned_put(key)
    except StorageError:
        raise StorageDown() from None
    return {"upload_url": url, "key": key, "headers": {"Content-Type": storage.PHOTO_CONTENT_TYPE}}


def confirm_upload(stop: RouteStop, key: str) -> None:
    """Validates the uploaded object and records it as the stop's photo."""
    _require_enabled()
    prefix = key_prefix(stop)
    if not (key.startswith(prefix) and _KEY_NAME.match(key[len(prefix):])):
        raise BadRequest("La foto no corresponde a esta parada.")

    old_key = ""
    try:
        with transaction.atomic():
            locked = RouteStop.objects.select_for_update().get(pk=stop.pk)
            if locked.photo_key == key:
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

            old_key = locked.photo_key
            locked.photo_key = key
            locked.photo_uploaded_at = timezone.now()
            locked.save(update_fields=["photo_key", "photo_uploaded_at"])
    except StorageError:
        raise StorageDown() from None

    # Only after the new photo is saved: a failure here must not lose it.
    if old_key and old_key != key:
        try:
            storage.delete(old_key)
        except StorageError:
            logger.warning("Could not delete replaced photo %s", old_key)


def view_url(stop: RouteStop) -> str | None:
    """Temporary link to see the stop's photo, or None when there is nothing to show."""
    if not stop.photo_key or not storage.is_configured():
        return None
    try:
        return storage.presigned_get(stop.photo_key)
    except StorageError:
        logger.warning("Could not sign a view URL for %s", stop.photo_key)
        return None
