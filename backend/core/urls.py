from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from core import views

router = DefaultRouter()
router.register("orders", views.OrderViewSet, basename="order")
router.register("drivers", views.DriverViewSet, basename="driver")
router.register("routes", views.RouteViewSet, basename="route")

urlpatterns = [
    path("auth/token/", TokenObtainPairView.as_view(), name="token"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/demo/", views.demo_login, name="demo-login"),
    path("demo/reset/", views.demo_reset, name="demo-reset"),
    path("business/me/", views.business_me, name="business-me"),
    *router.urls,
]
