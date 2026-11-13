import pytest

from core.models import Driver, Order, Route

pytestmark = pytest.mark.django_db

NEW_ORDER = {"customer_name": "Doña Rosa", "address": "Cl. 5 # 10-20", "lat": 3.44, "lng": -76.52, "notes": ""}


# --- orders: create -------------------------------------------------------


def test_create_order_starts_pending_in_the_users_business(client_a, business_a):
    response = client_a.post("/api/orders/", NEW_ORDER, format="json")

    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    assert Order.objects.get().business == business_a


def test_create_order_ignores_a_business_sent_by_the_client(client_a, business_a, business_b):
    client_a.post("/api/orders/", {**NEW_ORDER, "business": business_b.id}, format="json")

    assert Order.objects.get().business == business_a


def test_create_order_ignores_a_status_sent_by_the_client(client_a):
    response = client_a.post("/api/orders/", {**NEW_ORDER, "status": "delivered"}, format="json")

    assert response.json()["status"] == "pending"


@pytest.mark.parametrize("field,value", [("lat", 95), ("lat", -90.1), ("lng", 200), ("lng", -180.5)])
def test_create_order_rejects_out_of_range_coordinates(client_a, field, value):
    response = client_a.post("/api/orders/", {**NEW_ORDER, field: value}, format="json")

    assert response.status_code == 400
    assert field in response.json()


def test_create_order_requires_a_location(client_a):
    payload = {k: v for k, v in NEW_ORDER.items() if k not in ("lat", "lng")}

    assert client_a.post("/api/orders/", payload, format="json").status_code == 400


def test_order_limit_per_business(client_a, business_a, make_order):
    Order.objects.bulk_create(
        Order(business=business_a, customer_name=f"C{i}", address="x", lat=3.4, lng=-76.5) for i in range(200)
    )

    response = client_a.post("/api/orders/", NEW_ORDER, format="json")

    assert response.status_code == 400
    assert "Límite de 200 pedidos" in response.json()["detail"]
    assert Order.objects.count() == 200


def test_requests_without_token_are_rejected(anon_client):
    assert anon_client.get("/api/orders/").status_code == 401
    assert anon_client.post("/api/orders/", NEW_ORDER, format="json").status_code == 401


# --- orders: isolation between businesses --------------------------------


def test_list_only_shows_own_orders(client_a, business_a, business_b, make_order):
    mine = make_order(business_a, customer_name="Mío")
    make_order(business_b, customer_name="Ajeno")

    data = client_a.get("/api/orders/").json()

    assert [order["id"] for order in data] == [mine.id]


def test_cannot_read_update_or_delete_another_business_order(client_a, business_b, make_order):
    foreign = make_order(business_b)
    url = f"/api/orders/{foreign.id}/"

    assert client_a.get(url).status_code == 404
    assert client_a.patch(url, {"customer_name": "Hackeado"}, format="json").status_code == 404
    assert client_a.delete(url).status_code == 404
    foreign.refresh_from_db()
    assert foreign.customer_name == "Cliente"


# --- orders: list, update, delete ----------------------------------------


def test_filter_by_status(client_a, business_a, make_order):
    pending = make_order(business_a)
    make_order(business_a, status=Order.Status.DELIVERED)

    data = client_a.get("/api/orders/?status=pending").json()

    assert [order["id"] for order in data] == [pending.id]


def test_list_is_newest_first(client_a, business_a, make_order):
    first = make_order(business_a)
    second = make_order(business_a)

    data = client_a.get("/api/orders/").json()

    assert [order["id"] for order in data] == [second.id, first.id]


def test_update_pending_order(client_a, business_a, make_order):
    order = make_order(business_a)

    response = client_a.patch(f"/api/orders/{order.id}/", {"notes": "Tocar el timbre"}, format="json")

    assert response.status_code == 200
    order.refresh_from_db()
    assert order.notes == "Tocar el timbre"


def test_delete_pending_order(client_a, business_a, make_order):
    order = make_order(business_a)

    assert client_a.delete(f"/api/orders/{order.id}/").status_code == 204
    assert Order.objects.count() == 0


@pytest.mark.parametrize("status", [Order.Status.ASSIGNED, Order.Status.DELIVERED])
def test_cannot_delete_an_order_that_is_on_a_route(client_a, business_a, make_order, status):
    order = make_order(business_a, status=status)

    response = client_a.delete(f"/api/orders/{order.id}/")

    assert response.status_code == 409
    assert Order.objects.filter(id=order.id).exists()


def test_cannot_move_an_order_that_is_on_a_route(client_a, business_a, make_order):
    order = make_order(business_a, status=Order.Status.ASSIGNED)

    response = client_a.patch(f"/api/orders/{order.id}/", {"lat": 3.5}, format="json")

    assert response.status_code == 409
    order.refresh_from_db()
    assert order.lat == 3.45


# --- drivers --------------------------------------------------------------


def test_driver_crud(client_a, business_a):
    created = client_a.post("/api/drivers/", {"name": "Pedro", "phone": "311"}, format="json")
    assert created.status_code == 201
    driver_id = created.json()["id"]
    assert Driver.objects.get(id=driver_id).business == business_a

    assert client_a.patch(f"/api/drivers/{driver_id}/", {"phone": "322"}, format="json").status_code == 200
    assert client_a.get("/api/drivers/").json()[0]["phone"] == "322"
    assert client_a.delete(f"/api/drivers/{driver_id}/").status_code == 204


def test_drivers_are_isolated_between_businesses(client_a, business_b, make_driver):
    foreign = make_driver(business_b)

    assert client_a.get("/api/drivers/").json() == []
    assert client_a.get(f"/api/drivers/{foreign.id}/").status_code == 404
    assert client_a.delete(f"/api/drivers/{foreign.id}/").status_code == 404


def test_cannot_delete_a_driver_with_routes(client_a, business_a, make_driver):
    driver = make_driver(business_a)
    Route.objects.create(business=business_a, driver=driver, date="2026-11-13", total_km=1, naive_km=2)

    response = client_a.delete(f"/api/drivers/{driver.id}/")

    assert response.status_code == 409
    assert Driver.objects.filter(id=driver.id).exists()


def test_user_without_business_is_forbidden(db):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient

    user = get_user_model().objects.create_user(username="solo-admin", password="x")
    client = APIClient()
    client.force_authenticate(user=user)

    assert client.get("/api/orders/").status_code == 403
