import datetime

import httpx
import pytest
from django.utils import timezone

from core import optimizer_client
from core.models import Order, Route, RouteStop
from core.optimizer_client import OptimizerResult, OptimizerUnavailable, optimize_route

pytestmark = pytest.mark.django_db

UNAVAILABLE_MESSAGE = "El servicio de optimización no está disponible. Intenta de nuevo en unos segundos."


@pytest.fixture
def fake_optimizer(monkeypatch):
    """Replaces the HTTP call with one that returns the stops in reverse order."""
    calls = []

    def _fake(depot, stops, token):
        calls.append({"depot": depot, "stops": stops, "token": token})
        return OptimizerResult(order=[s["id"] for s in reversed(stops)], optimized_km=10.5, naive_km=14.25)

    monkeypatch.setattr("core.views.optimize_route", _fake)
    return calls


@pytest.fixture
def broken_optimizer(monkeypatch):
    def _broken(depot, stops, token):
        raise OptimizerUnavailable("down")

    monkeypatch.setattr("core.views.optimize_route", _broken)


@pytest.fixture
def scenario(business_a, make_order, make_driver):
    """A driver and three pending orders for business A."""
    driver = make_driver(business_a)
    orders = [make_order(business_a, customer_name=f"Cliente {i}", lat=3.40 + i * 0.01) for i in range(3)]
    return driver, orders


def create_route(client, driver, orders, **extra):
    payload = {"driver": driver.id, "order_ids": [o.id for o in orders], **extra}
    return client.post("/api/routes/", payload, format="json")


def assert_nothing_was_saved():
    assert Route.objects.count() == 0
    assert RouteStop.objects.count() == 0
    assert not Order.objects.exclude(status=Order.Status.PENDING).exists()


# --- creating a route -----------------------------------------------------


def test_create_route_saves_stops_in_the_optimized_order(client_a, scenario, fake_optimizer):
    driver, orders = scenario

    response = create_route(client_a, driver, orders)

    assert response.status_code == 201
    data = response.json()
    assert [stop["order"]["id"] for stop in data["stops"]] == [o.id for o in reversed(orders)]
    assert [stop["sequence"] for stop in data["stops"]] == [1, 2, 3]
    assert data["total_km"] == 10.5
    assert data["naive_km"] == 14.25
    assert data["saved_km"] == 3.75
    assert data["status"] == "planned"
    assert data["driver"] == {"id": driver.id, "name": driver.name}
    assert data["depot"] == {"lat": 3.4516, "lng": -76.5320}
    assert set(Order.objects.values_list("status", flat=True)) == {"assigned"}


def test_create_route_sends_depot_stops_and_the_users_token(client_a, business_a, scenario, fake_optimizer):
    driver, orders = scenario

    create_route(client_a, driver, orders, HTTP_AUTHORIZATION="Bearer ignored")

    call = fake_optimizer[0]
    assert call["depot"] == (business_a.depot_lat, business_a.depot_lng)
    assert call["stops"] == [{"id": o.id, "lat": o.lat, "lng": o.lng} for o in orders]


def test_create_route_defaults_to_today(client_a, scenario, fake_optimizer):
    driver, orders = scenario

    data = create_route(client_a, driver, orders).json()

    assert data["date"] == timezone.localdate().isoformat()


def test_create_route_accepts_a_date(client_a, scenario, fake_optimizer):
    driver, orders = scenario

    data = create_route(client_a, driver, orders, date="2026-12-24").json()

    assert data["date"] == "2026-12-24"


def test_empty_order_ids_are_rejected(client_a, scenario, fake_optimizer):
    driver, _ = scenario

    response = create_route(client_a, driver, [])

    assert response.status_code == 400
    assert_nothing_was_saved()


def test_repeated_order_ids_are_rejected(client_a, scenario, fake_optimizer):
    driver, orders = scenario

    response = create_route(client_a, driver, [orders[0], orders[0]])

    assert response.status_code == 400
    assert_nothing_was_saved()


def test_order_of_another_business_is_rejected(client_a, business_b, scenario, make_order, fake_optimizer):
    driver, orders = scenario
    foreign = make_order(business_b)

    response = create_route(client_a, driver, [orders[0], foreign])

    assert response.status_code == 400
    assert_nothing_was_saved()
    assert fake_optimizer == []


def test_order_already_assigned_is_rejected(client_a, business_a, scenario, make_order, fake_optimizer):
    driver, orders = scenario
    taken = make_order(business_a, status=Order.Status.ASSIGNED)

    response = create_route(client_a, driver, [orders[0], taken])

    assert response.status_code == 400
    assert Route.objects.count() == 0
    orders[0].refresh_from_db()
    assert orders[0].status == Order.Status.PENDING


def test_driver_of_another_business_is_rejected(client_a, business_b, scenario, make_driver, fake_optimizer):
    _, orders = scenario
    foreign_driver = make_driver(business_b)

    response = create_route(client_a, foreign_driver, orders)

    assert response.status_code == 400
    assert_nothing_was_saved()


def test_more_than_one_hundred_orders_are_rejected(client_a, business_a, make_driver, fake_optimizer):
    driver = make_driver(business_a)
    Order.objects.bulk_create(
        Order(business=business_a, customer_name=f"C{i}", address="x", lat=3.4, lng=-76.5) for i in range(101)
    )

    response = create_route(client_a, driver, list(Order.objects.all()))

    assert response.status_code == 400
    assert_nothing_was_saved()


def test_creating_the_same_route_twice_fails_the_second_time(client_a, scenario, fake_optimizer):
    driver, orders = scenario

    first = create_route(client_a, driver, orders)
    second = create_route(client_a, driver, orders)

    assert first.status_code == 201
    assert second.status_code == 400
    assert Route.objects.count() == 1
    assert RouteStop.objects.count() == 3


def test_optimizer_down_returns_502_and_saves_nothing(client_a, scenario, broken_optimizer):
    driver, orders = scenario

    response = create_route(client_a, driver, orders)

    assert response.status_code == 502
    assert response.json() == {"detail": UNAVAILABLE_MESSAGE}
    assert_nothing_was_saved()


# --- reading routes -------------------------------------------------------


def test_list_routes_newest_first_without_stops(client_a, business_a, scenario, make_order, fake_optimizer):
    driver, orders = scenario
    first = create_route(client_a, driver, orders[:1]).json()
    second = create_route(client_a, driver, orders[1:]).json()

    data = client_a.get("/api/routes/").json()

    assert [route["id"] for route in data] == [second["id"], first["id"]]
    assert "stops" not in data[0]
    assert data[0]["stops_count"] == 2
    assert data[0]["delivered_count"] == 0


def test_routes_are_isolated_between_businesses(client_a, client_b, scenario, fake_optimizer):
    driver, orders = scenario
    route_id = create_route(client_a, driver, orders).json()["id"]

    assert client_b.get("/api/routes/").json() == []
    assert client_b.get(f"/api/routes/{route_id}/").status_code == 404


# --- delivering -----------------------------------------------------------


@pytest.fixture
def route(client_a, scenario, fake_optimizer):
    driver, orders = scenario
    return create_route(client_a, driver, orders).json()


def deliver(client, route, index):
    stop_id = route["stops"][index]["id"]
    return client.post(f"/api/routes/{route['id']}/stops/{stop_id}/deliver/")


def test_first_delivery_puts_the_route_in_progress(client_a, route):
    response = deliver(client_a, route, 0)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "in_progress"
    assert data["stops"][0]["delivered_at"] is not None
    assert data["stops"][1]["delivered_at"] is None
    assert Order.objects.get(id=route["stops"][0]["order"]["id"]).status == Order.Status.DELIVERED


def test_delivering_twice_changes_nothing(client_a, route):
    first = deliver(client_a, route, 0).json()
    second = deliver(client_a, route, 0)

    assert second.status_code == 200
    assert second.json()["stops"][0]["delivered_at"] == first["stops"][0]["delivered_at"]


def test_delivering_every_stop_completes_the_route(client_a, route):
    for index in range(3):
        last = deliver(client_a, route, index)

    assert last.json()["status"] == "done"
    assert set(Order.objects.values_list("status", flat=True)) == {"delivered"}


def test_cannot_deliver_a_stop_of_another_business(client_b, route):
    response = deliver(client_b, route, 0)

    assert response.status_code == 404
    assert RouteStop.objects.filter(delivered_at__isnull=False).count() == 0


def test_stop_must_belong_to_the_route_in_the_url(client_a, business_a, route, make_order, make_driver, fake_optimizer):
    other = create_route(client_a, make_driver(business_a, "Otro"), [make_order(business_a)]).json()
    stop_of_other = other["stops"][0]["id"]

    response = client_a.post(f"/api/routes/{route['id']}/stops/{stop_of_other}/deliver/")

    assert response.status_code == 404


# --- demo reset -----------------------------------------------------------


def test_demo_reset_restores_the_data(anon_client, fake_optimizer):
    access = anon_client.post("/api/auth/demo/").json()["access"]
    anon_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    orders = anon_client.get("/api/orders/").json()
    driver = anon_client.get("/api/drivers/").json()[0]
    anon_client.post("/api/routes/", {"driver": driver["id"], "order_ids": [o["id"] for o in orders[:4]]}, format="json")
    assert Route.objects.count() == 1

    response = anon_client.post("/api/demo/reset/")

    assert response.status_code == 204
    assert Route.objects.count() == 0
    assert Order.objects.filter(status=Order.Status.PENDING).count() == 12


def test_demo_reset_is_forbidden_for_other_users(client_a, business_a, make_order):
    make_order(business_a)

    assert client_a.post("/api/demo/reset/").status_code == 403
    assert Order.objects.count() == 1


# --- optimizer client (real code, fake network) ---------------------------

STOPS = [{"id": 5, "lat": 3.41, "lng": -76.54}, {"id": 9, "lat": 3.45, "lng": -76.50}]
DEPOT = (3.40, -76.55)


def use_transport(monkeypatch, handler):
    monkeypatch.setattr(optimizer_client, "_transport", httpx.MockTransport(handler))


def test_client_posts_the_contract_and_forwards_the_token(monkeypatch, settings):
    settings.OPTIMIZER_URL = "http://optimizer.test"
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"order": [9, 5], "optimized_km": 1.5, "naive_km": 2.5, "stops_count": 2})

    use_transport(monkeypatch, handler)

    result = optimize_route(DEPOT, STOPS, "the-token")

    assert result == OptimizerResult(order=[9, 5], optimized_km=1.5, naive_km=2.5)
    assert seen["url"] == "http://optimizer.test/optimize"
    assert seen["auth"] == "Bearer the-token"
    assert seen["body"] == {"depot": {"lat": 3.40, "lng": -76.55}, "stops": STOPS}


def test_client_raises_on_server_error(monkeypatch):
    use_transport(monkeypatch, lambda request: httpx.Response(500, text="boom"))

    with pytest.raises(OptimizerUnavailable):
        optimize_route(DEPOT, STOPS, "t")


def test_client_raises_on_timeout(monkeypatch):
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    use_transport(monkeypatch, handler)

    with pytest.raises(OptimizerUnavailable):
        optimize_route(DEPOT, STOPS, "t")


def test_client_raises_on_connection_error(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    use_transport(monkeypatch, handler)

    with pytest.raises(OptimizerUnavailable):
        optimize_route(DEPOT, STOPS, "t")


@pytest.mark.parametrize(
    "payload",
    [
        {"order": [9, 777], "optimized_km": 1.0, "naive_km": 2.0},  # foreign id
        {"order": [9], "optimized_km": 1.0, "naive_km": 2.0},  # missing id
        {"order": [9, 9], "optimized_km": 1.0, "naive_km": 2.0},  # repeated id
        {"optimized_km": 1.0, "naive_km": 2.0},  # no order at all
        {"order": [9, 5], "optimized_km": "abc", "naive_km": 2.0},  # not a number
    ],
)
def test_client_raises_when_the_answer_is_not_a_valid_route(monkeypatch, payload):
    use_transport(monkeypatch, lambda request: httpx.Response(200, json=payload))

    with pytest.raises(OptimizerUnavailable):
        optimize_route(DEPOT, STOPS, "t")


def test_client_raises_when_the_answer_is_not_json(monkeypatch):
    use_transport(monkeypatch, lambda request: httpx.Response(200, text="<html>gateway</html>"))

    with pytest.raises(OptimizerUnavailable):
        optimize_route(DEPOT, STOPS, "t")
