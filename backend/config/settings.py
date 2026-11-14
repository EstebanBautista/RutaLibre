"""Django settings for the RutaLibre backend.

Everything that changes between environments comes from environment
variables (see .env.example). Local development needs none of them: it
falls back to SQLite and development-only keys.
"""

import os
import urllib.parse
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_list(name: str) -> list[str]:
    """Reads a comma-separated environment variable as a clean list."""
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

# Vercel sets VERCEL=1 on its builds and functions. Outside production the
# keys below have insecure defaults so the project runs with zero setup.
IS_PRODUCTION = os.environ.get("VERCEL") == "1"
_DEV_KEY = "dev-only-insecure-key-do-not-use-in-production-0123456789abcdef"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or ("" if IS_PRODUCTION else _DEV_KEY)
# Signs the JWTs. The optimizer service verifies them with this same value.
JWT_SIGNING_KEY = os.environ.get("JWT_SIGNING_KEY") or ("" if IS_PRODUCTION else _DEV_KEY)

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver", ".vercel.app", *env_list("ALLOWED_HOSTS")]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Database: Postgres when DATABASE_URL is set, SQLite otherwise ---------

if os.environ.get("DATABASE_URL"):
    _url = urllib.parse.urlparse(os.environ["DATABASE_URL"])
    _query = dict(urllib.parse.parse_qsl(_url.query))
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _url.path.lstrip("/"),
            "USER": urllib.parse.unquote(_url.username or ""),
            "PASSWORD": urllib.parse.unquote(_url.password or ""),
            "HOST": _url.hostname,
            "PORT": _url.port or 5432,
            "OPTIONS": {"sslmode": _query.get("sslmode", "require")},
            # Serverless functions are short-lived: do not hold connections open.
            "CONN_MAX_AGE": 0,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- API -------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

SIMPLE_JWT = {
    "ALGORITHM": "HS256",
    "SIGNING_KEY": JWT_SIGNING_KEY,
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

# Browser origins allowed to call the API. Locally, with nothing configured,
# the frontend served on port 5500 is allowed so the README steps just work.
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS") or (
    [] if IS_PRODUCTION else ["http://localhost:5500", "http://127.0.0.1:5500"]
)

# --- Optimizer service -----------------------------------------------------

OPTIMIZER_URL = os.environ.get("OPTIMIZER_URL", "http://localhost:8001").rstrip("/")
OPTIMIZER_TIMEOUT_SECONDS = 10.0

# --- Delivery photos: S3-compatible storage (Backblaze B2 in production) ----
# If any value is missing, photos are simply turned off.

S3 = {
    "endpoint_url": os.environ.get("S3_ENDPOINT_URL", ""),
    "region": os.environ.get("S3_REGION", ""),
    "bucket": os.environ.get("S3_BUCKET", ""),
    "access_key_id": os.environ.get("S3_ACCESS_KEY_ID", ""),
    "secret_access_key": os.environ.get("S3_SECRET_ACCESS_KEY", ""),
}

# --- Production hardening --------------------------------------------------

if IS_PRODUCTION:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    CSRF_TRUSTED_ORIGINS = ["https://*.vercel.app"]
