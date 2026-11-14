import boto3
import pytest
from moto import mock_aws

from core import demo, storage
from core.models import Order, Route, RouteStop
from core.storage import StorageError

pytestmark = pytest.mark.django_db

BUCKET = "rutalibre-test"
CONFIG = {
    # A regional AWS endpoint: moto recognizes it as S3.
    "endpoint_url": "https://s3.us-east-1.amazonaws.com",
    "region": "us-east-1",
    "bucket": BUCKET,
    "access_key_id": "testing",
    "secret_access_key": "testing",
}
EMPTY_CONFIG = {name: "" for name in CONFIG}

NO_OBJECT = "No se encontró la foto subida. Vuelve a intentarlo."
WRONG_STOP = "La foto no corresponde a esta parada."
TOO_BIG = "La foto supera 2 MB."
NOT_JPEG = "La foto debe ser JPEG."
DISABLED = "Las fotos de evidencia no están configuradas en este servidor."
STORAGE_DOWN = "El almacenamiento de fotos no responde. La entrega no se ve afectada; intenta de nuevo."


@pytest.fixture
def s3(settings):
    """A mocked S3 with an empty bucket, and settings that point at it."""
    with mock_aws():
        settings.S3 = dict(CONFIG)
        client = boto3.client("s3", region_name="us-east-1", aws_access_key_id="testing", aws_secret_access_key="testing")
        client.create_bucket(Bucket=BUCKET)
        storage._client.cache_clear()
        yield client
        storage._client.cache_clear()


@pytest.fixture
def route(business_a, make_driver, make_order):
    """A route of business A with two stops."""
    driver = make_driver(business_a)
    route = Route.objects.create(business=business_a, driver=driver, date="2026-11-14", total_km=5, naive_km=9)
    for position in (1, 2):
        order = make_order(business_a, status=Order.Status.ASSIGNED)
        RouteStop.objects.create(route=route, order=order, sequence=position)
    return route


def stop_ids(route):
    return [stop.id for stop in route.stops.all()]


def upload_url(client, route, stop_id):
    return client.post(f"/api/routes/{route.id}/stops/{stop_id}/photo/upload-url/")


def confirm(client, route, stop_id, key):
    return client.post(f"/api/routes/{route.id}/stops/{stop_id}/photo/", {"key": key}, format="json")


def put_object(s3, key, size=100, content_type="image/jpeg"):
    s3.put_object(Bucket=BUCKET, Key=key, Body=b"x" * size, ContentType=content_type)


def exists(s3, key):
    return storage.head(key) is not None


def stop_in(response, stop_id):
    return next(stop for stop in response.json()["stops"] if stop["id"] == stop_id)


def prefix_for(business, route, stop_id):
    return f"businesses/{business.id}/routes/{route.id}/stops/{stop_id}/"


def fresh_key(business, route, stop_id, name="a" * 32):
    return f"{prefix_for(business, route, stop_id)}{name}.jpg"


# --- asking for an upload URL --------------------------------------------


def test_upload_url_has_a_key_inside_the_stops_prefix(client_a, business_a, route, s3):
    first, _ = stop_ids(route)

    response = upload_url(client_a, route, first)

    assert response.status_code == 200
    data = response.json()
    assert data["key"].startswith(prefix_for(business_a, route, first))
    assert data["key"].endswith(".jpg")
    assert data["headers"] == {"Content-Type": "image/jpeg"}
    assert "X-Amz-Signature=" in data["upload_url"]


def test_each_upload_url_gets_a_new_key(client_a, route, s3):
    first, _ = stop_ids(route)

    keys = {upload_url(client_a, route, first).json()["key"] for _ in range(3)}

    assert len(keys) == 3


# --- confirming an upload -------------------------------------------------


def test_upload_then_confirm_stores_the_photo(client_a, route, s3):
    first, _ = stop_ids(route)
    key = upload_url(client_a, route, first).json()["key"]
    put_object(s3, key)

    response = confirm(client_a, route, first, key)

    assert response.status_code == 200
    stop = stop_in(response, first)
    assert "X-Amz-Signature=" in stop["photo_url"]
    assert stop["photo_uploaded_at"] is not None
    assert RouteStop.objects.get(pk=first).photo_key == key


def test_confirming_without_uploading_is_rejected(client_a, business_a, route, s3):
    first, _ = stop_ids(route)

    response = confirm(client_a, route, first, fresh_key(business_a, route, first))

    assert response.status_code == 400
    assert response.json() == {"detail": NO_OBJECT}
    assert RouteStop.objects.get(pk=first).photo_key == ""


def test_a_key_from_another_stop_is_rejected(client_a, business_a, route, s3):
    first, second = stop_ids(route)
    foreign_key = fresh_key(business_a, route, second)
    put_object(s3, foreign_key)

    response = confirm(client_a, route, first, foreign_key)

    assert response.status_code == 400
    assert response.json() == {"detail": WRONG_STOP}
    assert RouteStop.objects.get(pk=first).photo_key == ""


@pytest.mark.parametrize("suffix", ["../../other.jpg", "abc.jpg", "a" * 32 + ".png", "a" * 32 + ".jpg/extra"])
def test_keys_that_are_not_ours_are_rejected(client_a, business_a, route, s3, suffix):
    first, _ = stop_ids(route)

    response = confirm(client_a, route, first, prefix_for(business_a, route, first) + suffix)

    assert response.status_code == 400
    assert response.json() == {"detail": WRONG_STOP}


def test_a_missing_key_in_the_body_is_rejected(client_a, route, s3):
    first, _ = stop_ids(route)

    response = client_a.post(f"/api/routes/{route.id}/stops/{first}/photo/", {}, format="json")

    assert response.status_code == 400


def test_a_photo_over_two_megabytes_is_rejected_and_deleted(client_a, business_a, route, s3):
    first, _ = stop_ids(route)
    key = fresh_key(business_a, route, first)
    put_object(s3, key, size=2 * 1024 * 1024 + 1)

    response = confirm(client_a, route, first, key)

    assert response.status_code == 400
    assert response.json() == {"detail": TOO_BIG}
    assert not exists(s3, key)
    assert RouteStop.objects.get(pk=first).photo_key == ""


def test_a_photo_of_exactly_two_megabytes_is_accepted(client_a, business_a, route, s3):
    first, _ = stop_ids(route)
    key = fresh_key(business_a, route, first)
    put_object(s3, key, size=2 * 1024 * 1024)

    assert confirm(client_a, route, first, key).status_code == 200


def test_a_file_that_is_not_jpeg_is_rejected_and_deleted(client_a, business_a, route, s3):
    first, _ = stop_ids(route)
    key = fresh_key(business_a, route, first)
    put_object(s3, key, content_type="image/png")

    response = confirm(client_a, route, first, key)

    assert response.status_code == 400
    assert response.json() == {"detail": NOT_JPEG}
    assert not exists(s3, key)


def test_a_new_photo_replaces_and_deletes_the_old_one(client_a, business_a, route, s3):
    first, _ = stop_ids(route)
    old_key = fresh_key(business_a, route, first, "a" * 32)
    new_key = fresh_key(business_a, route, first, "b" * 32)
    put_object(s3, old_key)
    put_object(s3, new_key)

    confirm(client_a, route, first, old_key)
    confirm(client_a, route, first, new_key)

    assert not exists(s3, old_key)
    assert exists(s3, new_key)
    assert RouteStop.objects.get(pk=first).photo_key == new_key


def test_confirming_the_same_key_twice_keeps_the_photo(client_a, business_a, route, s3):
    first, _ = stop_ids(route)
    key = fresh_key(business_a, route, first)
    put_object(s3, key)

    first_try = confirm(client_a, route, first, key)
    second_try = confirm(client_a, route, first, key)

    assert first_try.status_code == 200
    assert second_try.status_code == 200
    assert exists(s3, key)
    assert RouteStop.objects.get(pk=first).photo_key == key


def test_a_photo_does_not_change_the_delivery_state(client_a, business_a, route, s3):
    first, _ = stop_ids(route)
    key = fresh_key(business_a, route, first)
    put_object(s3, key)

    response = confirm(client_a, route, first, key)

    assert stop_in(response, first)["delivered_at"] is None
    assert response.json()["status"] == "planned"


# --- isolation ------------------------------------------------------------


def test_another_business_cannot_ask_for_an_upload_url(client_b, route, s3):
    first, _ = stop_ids(route)

    assert upload_url(client_b, route, first).status_code == 404


def test_another_business_cannot_confirm_a_photo(client_b, business_a, route, s3):
    first, _ = stop_ids(route)
    key = fresh_key(business_a, route, first)
    put_object(s3, key)

    assert confirm(client_b, route, first, key).status_code == 404
    assert RouteStop.objects.get(pk=first).photo_key == ""


def test_a_stop_must_belong_to_the_route_in_the_url(client_a, business_a, route, make_driver, make_order, s3):
    first, _ = stop_ids(route)
    other_route = Route.objects.create(
        business=business_a, driver=route.driver, date="2026-11-14", total_km=1, naive_km=1
    )

    assert client_a.post(f"/api/routes/{other_route.id}/stops/{first}/photo/upload-url/").status_code == 404


def test_requests_without_a_token_are_rejected(anon_client, route, s3):
    first, _ = stop_ids(route)

    assert upload_url(anon_client, route, first).status_code == 401


# --- photos turned off or storage failing --------------------------------


@pytest.fixture
def photos_off(settings):
    settings.S3 = dict(EMPTY_CONFIG)
    storage._client.cache_clear()


def test_without_configuration_the_upload_url_is_a_503(client_a, route, photos_off):
    first, _ = stop_ids(route)

    response = upload_url(client_a, route, first)

    assert response.status_code == 503
    assert response.json() == {"detail": DISABLED}


def test_without_configuration_confirming_is_a_503(client_a, business_a, route, photos_off):
    first, _ = stop_ids(route)

    assert confirm(client_a, route, first, fresh_key(business_a, route, first)).status_code == 503


def test_without_configuration_the_business_says_photos_are_disabled(client_a, photos_off):
    assert client_a.get("/api/business/me/").json()["photos_enabled"] is False


def test_with_configuration_the_business_says_photos_are_enabled(client_a, s3):
    assert client_a.get("/api/business/me/").json()["photos_enabled"] is True


def test_without_configuration_the_route_detail_has_no_photo_urls(client_a, route, photos_off):
    RouteStop.objects.update(photo_key="businesses/1/x.jpg")

    data = client_a.get(f"/api/routes/{route.id}/").json()

    assert all(stop["photo_url"] is None for stop in data["stops"])


def test_without_configuration_delivering_still_works(client_a, route, photos_off):
    first, _ = stop_ids(route)

    response = client_a.post(f"/api/routes/{route.id}/stops/{first}/deliver/")

    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


def test_a_storage_failure_when_signing_is_a_502(client_a, route, s3, monkeypatch):
    first, _ = stop_ids(route)

    def broken(*args, **kwargs):
        raise StorageError("down")

    monkeypatch.setattr(storage, "presigned_put", broken)

    response = upload_url(client_a, route, first)

    assert response.status_code == 502
    assert response.json() == {"detail": STORAGE_DOWN}


def test_a_storage_failure_when_confirming_is_a_502(client_a, business_a, route, s3, monkeypatch):
    first, _ = stop_ids(route)

    def broken(key):
        raise StorageError("down")

    monkeypatch.setattr(storage, "head", broken)

    response = confirm(client_a, route, first, fresh_key(business_a, route, first))

    assert response.status_code == 502
    assert response.json() == {"detail": STORAGE_DOWN}
    assert RouteStop.objects.get(pk=first).photo_key == ""


def test_a_storage_failure_does_not_break_the_route_detail_or_delivery(client_a, route, s3, monkeypatch):
    first, _ = stop_ids(route)
    RouteStop.objects.filter(pk=first).update(photo_key="businesses/1/x.jpg")

    def broken(*args, **kwargs):
        raise StorageError("down")

    monkeypatch.setattr(storage, "presigned_get", broken)

    detail = client_a.get(f"/api/routes/{route.id}/")
    delivery = client_a.post(f"/api/routes/{route.id}/stops/{first}/deliver/")

    assert detail.status_code == 200
    assert stop_in(detail, first)["photo_url"] is None
    assert delivery.status_code == 200


# --- demo reset -----------------------------------------------------------


def test_reset_demo_deletes_the_demo_photos_and_only_those(s3):
    user = demo.ensure_demo()
    demo_prefix = f"businesses/{user.business.id}/"
    put_object(s3, demo_prefix + "routes/1/stops/1/" + "a" * 32 + ".jpg")
    put_object(s3, demo_prefix + "routes/1/stops/2/" + "b" * 32 + ".jpg")
    put_object(s3, "businesses/99999/routes/1/stops/1/" + "c" * 32 + ".jpg")

    demo.reset_demo()

    keys = [item["Key"] for item in s3.list_objects_v2(Bucket=BUCKET).get("Contents", [])]
    assert keys == ["businesses/99999/routes/1/stops/1/" + "c" * 32 + ".jpg"]


def test_reset_demo_still_restores_the_data_when_the_bucket_fails(s3, monkeypatch):
    demo.ensure_demo()
    Order.objects.all().delete()

    def broken(prefix):
        raise StorageError("down")

    monkeypatch.setattr(storage, "delete_prefix", broken)

    demo.reset_demo()

    assert Order.objects.filter(status=Order.Status.PENDING).count() == 12


def test_reset_demo_without_configuration_does_not_touch_storage(photos_off, monkeypatch):
    def forbidden(prefix):
        raise AssertionError("storage must not be called when photos are off")

    monkeypatch.setattr(storage, "delete_prefix", forbidden)

    demo.reset_demo()

    assert Order.objects.count() == 12
