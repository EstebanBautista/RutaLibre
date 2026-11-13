import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.models import Business, Driver, Order


def make_business(username: str, name: str) -> Business:
    user = get_user_model().objects.create_user(username=username, password="clave-de-prueba-123")
    return Business.objects.create(owner=user, name=name, depot_lat=3.4516, depot_lng=-76.5320)


def client_for(business: Business) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=business.owner)
    return client


@pytest.fixture
def business_a(db):
    return make_business("ana", "Negocio A")


@pytest.fixture
def business_b(db):
    return make_business("beto", "Negocio B")


@pytest.fixture
def client_a(business_a):
    return client_for(business_a)


@pytest.fixture
def client_b(business_b):
    return client_for(business_b)


@pytest.fixture
def anon_client(db):
    return APIClient()


@pytest.fixture
def make_order():
    def _make(business: Business, **overrides) -> Order:
        fields = {
            "customer_name": "Cliente",
            "address": "Calle 1 # 2-3",
            "lat": 3.45,
            "lng": -76.53,
        }
        fields.update(overrides)
        return Order.objects.create(business=business, **fields)

    return _make


@pytest.fixture
def make_driver():
    def _make(business: Business, name: str = "Repartidor") -> Driver:
        return Driver.objects.create(business=business, name=name, phone="3000000000")

    return _make
