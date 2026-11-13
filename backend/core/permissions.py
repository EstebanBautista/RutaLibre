from rest_framework.permissions import BasePermission

from core.demo import is_demo_user


class HasBusiness(BasePermission):
    """Only users that own a business may use the API (an admin-only user has none)."""

    message = "Este usuario no tiene un negocio asociado."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated and hasattr(request.user, "business"))


class IsDemoUser(BasePermission):
    message = "Solo la cuenta demo puede restablecer sus datos."

    def has_permission(self, request, view) -> bool:
        return is_demo_user(request.user)
