import pytest

from tests.conftest import CROSSED_SQUARE, DEPOT, make_token


def body(stops=None, depot=None):
    return {"depot": depot or DEPOT, "stops": CROSSED_SQUARE if stops is None else stops}


# --- authentication -------------------------------------------------------


def test_request_without_token_is_rejected(client):
    assert client.post("/optimize", json=body()).status_code == 401


def test_token_signed_with_another_key_is_rejected(client):
    token = make_token(key="some-other-key-some-other-key-some-other-key")
    response = client.post("/optimize", json=body(), headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_expired_token_is_rejected(client):
    token = make_token(expires_in=-60)
    response = client.post("/optimize", json=body(), headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_refresh_token_is_rejected(client):
    token = make_token(token_type="refresh")
    response = client.post("/optimize", json=body(), headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_malformed_authorization_header_is_rejected(client):
    response = client.post("/optimize", json=body(), headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


# --- happy path -----------------------------------------------------------


def test_valid_request_returns_the_ids_in_optimized_order(client, auth_headers):
    response = client.post("/optimize", json=body(), headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert sorted(data["order"]) == [11, 22, 33, 44]
    assert data["optimized_km"] < data["naive_km"]
    assert data["stops_count"] == 4


def test_distances_are_rounded_to_three_decimals(client, auth_headers):
    data = client.post("/optimize", json=body(), headers=auth_headers).json()

    assert data["optimized_km"] == round(data["optimized_km"], 3)
    assert data["naive_km"] == round(data["naive_km"], 3)


def test_single_stop_is_accepted(client, auth_headers):
    response = client.post("/optimize", json=body(stops=CROSSED_SQUARE[:1]), headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["order"] == [11]


def test_one_hundred_stops_are_accepted(client, auth_headers):
    stops = [{"id": i, "lat": 3.35 + (i % 10) * 0.01, "lng": -76.60 + (i // 10) * 0.01} for i in range(100)]
    response = client.post("/optimize", json=body(stops=stops), headers=auth_headers)

    assert response.status_code == 200
    assert sorted(response.json()["order"]) == list(range(100))


def test_all_stops_on_the_same_point_give_zero_distance(client, auth_headers):
    stops = [{"id": i, "lat": DEPOT["lat"], "lng": DEPOT["lng"]} for i in range(5)]
    data = client.post("/optimize", json=body(stops=stops), headers=auth_headers).json()

    assert data["optimized_km"] == 0.0
    assert sorted(data["order"]) == [0, 1, 2, 3, 4]


# --- validation -----------------------------------------------------------


def test_empty_stops_are_rejected(client, auth_headers):
    assert client.post("/optimize", json=body(stops=[]), headers=auth_headers).status_code == 422


def test_more_than_one_hundred_stops_are_rejected(client, auth_headers):
    stops = [{"id": i, "lat": 3.4, "lng": -76.5} for i in range(101)]
    assert client.post("/optimize", json=body(stops=stops), headers=auth_headers).status_code == 422


@pytest.mark.parametrize(
    "stop",
    [
        {"id": 1, "lat": 91, "lng": -76.5},
        {"id": 1, "lat": -90.5, "lng": -76.5},
        {"id": 1, "lat": 3.4, "lng": -181},
        {"id": 1, "lat": 3.4, "lng": 180.1},
    ],
)
def test_out_of_range_coordinates_are_rejected(client, auth_headers, stop):
    assert client.post("/optimize", json=body(stops=[stop]), headers=auth_headers).status_code == 422


def test_out_of_range_depot_is_rejected(client, auth_headers):
    response = client.post("/optimize", json=body(depot={"lat": 120, "lng": 0}), headers=auth_headers)
    assert response.status_code == 422


def test_duplicate_ids_are_rejected(client, auth_headers):
    stops = [{"id": 7, "lat": 3.4, "lng": -76.5}, {"id": 7, "lat": 3.41, "lng": -76.51}]
    assert client.post("/optimize", json=body(stops=stops), headers=auth_headers).status_code == 422


def test_nan_coordinate_is_rejected(client, auth_headers):
    # NaN is not valid JSON, so it is sent as raw text the way a careless client would.
    raw = '{"depot": {"lat": 3.4, "lng": -76.5}, "stops": [{"id": 1, "lat": NaN, "lng": -76.5}]}'
    response = client.post(
        "/optimize", content=raw, headers={**auth_headers, "Content-Type": "application/json"}
    )
    assert response.status_code == 422


# --- service endpoints ----------------------------------------------------


def test_health_needs_no_token(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "engine": "wasm"}


def test_cors_allows_the_configured_origin(client):
    response = client.options(
        "/optimize",
        headers={
            "Origin": "http://localhost:5500",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5500"
