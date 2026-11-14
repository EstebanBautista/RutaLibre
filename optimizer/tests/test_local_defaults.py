"""Running locally with no environment variables must just work (README)."""
from tests.conftest import CROSSED_SQUARE, DEPOT, make_token

DEV_KEY = "dev-only-insecure-key-do-not-use-in-production-0123456789abcdef"
BODY = {"depot": DEPOT, "stops": CROSSED_SQUARE}


def test_without_a_key_locally_the_django_dev_key_is_accepted(client, monkeypatch):
    monkeypatch.delenv("JWT_SIGNING_KEY", raising=False)
    monkeypatch.delenv("VERCEL", raising=False)
    token = make_token(key=DEV_KEY)

    response = client.post("/optimize", json=BODY, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200


def test_without_a_key_in_production_everything_is_rejected(client, monkeypatch):
    monkeypatch.delenv("JWT_SIGNING_KEY", raising=False)
    monkeypatch.setenv("VERCEL", "1")
    token = make_token(key=DEV_KEY)

    response = client.post("/optimize", json=BODY, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
