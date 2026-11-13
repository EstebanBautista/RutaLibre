import jwt
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model

from core import demo
from core.models import Driver, Order, Route

pytestmark = pytest.mark.django_db


def demo_login(client):
    return client.post("/api/auth/demo/")


def test_demo_login_returns_tokens_and_creates_demo_data(anon_client):
    response = demo_login(anon_client)

    assert response.status_code == 200
    assert set(response.json()) == {"access", "refresh"}
    business = get_user_model().objects.get(username=demo.DEMO_USERNAME).business
    assert Order.objects.filter(business=business).count() == 12
    assert Driver.objects.filter(business=business).count() == 3


def test_demo_login_twice_does_not_duplicate_data(anon_client):
    demo_login(anon_client)
    demo_login(anon_client)

    assert Order.objects.count() == 12
    assert Driver.objects.count() == 3
    assert get_user_model().objects.filter(username=demo.DEMO_USERNAME).count() == 1


def test_demo_user_cannot_log_in_with_a_password(anon_client):
    demo_login(anon_client)

    response = anon_client.post("/api/auth/token/", {"username": "demo", "password": "demo"}, format="json")

    assert response.status_code == 401


def test_password_login_returns_tokens(anon_client, business_a):
    response = anon_client.post(
        "/api/auth/token/", {"username": "ana", "password": "clave-de-prueba-123"}, format="json"
    )

    assert response.status_code == 200
    assert set(response.json()) == {"access", "refresh"}


def test_business_me_requires_authentication(anon_client):
    assert anon_client.get("/api/business/me/").status_code == 401


def test_business_me_for_demo_user(anon_client):
    access = demo_login(anon_client).json()["access"]

    response = anon_client.get("/api/business/me/", HTTP_AUTHORIZATION=f"Bearer {access}")

    assert response.status_code == 200
    data = response.json()
    assert data["is_demo"] is True
    assert data["depot_lat"] == pytest.approx(3.4516)
    assert data["depot_lng"] == pytest.approx(-76.5320)


def test_business_me_for_regular_user_is_not_demo(client_a):
    data = client_a.get("/api/business/me/").json()

    assert data["name"] == "Negocio A"
    assert data["is_demo"] is False


def test_access_token_matches_the_contract_with_the_optimizer(anon_client):
    """The optimizer verifies HS256 with JWT_SIGNING_KEY and requires token_type == access."""
    access = demo_login(anon_client).json()["access"]

    claims = jwt.decode(access, settings.JWT_SIGNING_KEY, algorithms=["HS256"])

    assert claims["token_type"] == "access"
    assert "exp" in claims


def test_demo_orders_are_pending_and_inside_cali(anon_client):
    demo_login(anon_client)

    for order in Order.objects.all():
        assert order.status == Order.Status.PENDING
        assert 3.2 < order.lat < 3.6
        assert -76.7 < order.lng < -76.4


def test_reset_demo_restores_the_original_data(anon_client):
    demo_login(anon_client)
    doomed = list(Order.objects.values_list("id", flat=True)[:5])
    Order.objects.filter(id__in=doomed).delete()

    demo.reset_demo()

    assert Order.objects.filter(status=Order.Status.PENDING).count() == 12
    assert Driver.objects.count() == 3
    assert Route.objects.count() == 0


def test_seed_demo_command_is_idempotent(db):
    from django.core.management import call_command

    call_command("seed_demo")
    call_command("seed_demo")

    assert Order.objects.count() == 12
