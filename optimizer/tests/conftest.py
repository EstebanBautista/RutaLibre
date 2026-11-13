import os
import time

import jwt
import pytest

TEST_SIGNING_KEY = "test-signing-key-for-pytest-only-0123456789"

# The app reads its configuration from the environment at import time.
os.environ["JWT_SIGNING_KEY"] = TEST_SIGNING_KEY
os.environ["CORS_ALLOWED_ORIGINS"] = "http://localhost:5500"


def make_token(*, key: str = TEST_SIGNING_KEY, token_type: str = "access", expires_in: int = 300) -> str:
    """Builds a token shaped like the ones Django (simplejwt) issues."""
    now = int(time.time())
    payload = {"token_type": token_type, "user_id": 1, "iat": now, "exp": now + expires_in}
    return jwt.encode(payload, key, algorithm="HS256")


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {make_token()}"}


# Depot plus four stops on the corners of a square, listed in a crossing order.
DEPOT = {"lat": 3.40, "lng": -76.55}
CROSSED_SQUARE = [
    {"id": 11, "lat": 3.41, "lng": -76.54},
    {"id": 22, "lat": 3.45, "lng": -76.50},
    {"id": 33, "lat": 3.41, "lng": -76.50},
    {"id": 44, "lat": 3.45, "lng": -76.54},
]
