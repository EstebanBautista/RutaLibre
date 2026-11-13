from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def index(_request):
    """Small landing response so the API root is not a bare 404."""
    return JsonResponse({"service": "RutaLibre API", "api": "/api/", "admin": "/admin/"})


urlpatterns = [
    path("", index),
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
]
