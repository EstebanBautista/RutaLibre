"""Running locally with no environment variables must just work (README)."""
from django.conf import settings


def test_local_frontend_origin_is_allowed_by_default():
    assert "http://localhost:5500" in settings.CORS_ALLOWED_ORIGINS


def test_local_signing_key_matches_the_optimizer_dev_key():
    assert settings.JWT_SIGNING_KEY == "dev-only-insecure-key-do-not-use-in-production-0123456789abcdef"
