from django.db.models import ProtectedError
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from core.demo import ensure_demo
from core.exceptions import BadRequest, Conflict
from core.models import Driver, Order
from core.permissions import HasBusiness
from core.serializers import BusinessSerializer, DriverSerializer, OrderSerializer

MAX_ORDERS_PER_BUSINESS = 200


@api_view(["POST"])
@permission_classes([AllowAny])
def demo_login(request):
    """Public entry point: returns tokens for the shared demo account."""
    user = ensure_demo()
    refresh = RefreshToken.for_user(user)
    return Response({"access": str(refresh.access_token), "refresh": str(refresh)})


@api_view(["GET"])
@permission_classes([HasBusiness])
def business_me(request):
    return Response(BusinessSerializer(request.user.business).data)


class BusinessScopedMixin:
    """Limits a viewset to the records of the authenticated user's business.

    Filtering the queryset (instead of checking ownership per object) means a
    record of another business simply does not exist for this user: 404.
    """

    permission_classes = [HasBusiness]

    def get_queryset(self):
        return super().get_queryset().filter(business=self.request.user.business)

    def perform_create(self, serializer):
        serializer.save(business=self.request.user.business)


class OrderViewSet(BusinessScopedMixin, viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.query_params.get("status")
        if status_filter in Order.Status.values:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def perform_create(self, serializer):
        business = self.request.user.business
        if business.orders.count() >= MAX_ORDERS_PER_BUSINESS:
            raise BadRequest(f"Límite de {MAX_ORDERS_PER_BUSINESS} pedidos alcanzado. Restablece el demo.")
        serializer.save(business=business)

    def perform_update(self, serializer):
        order = serializer.instance
        moving = {"lat", "lng"} & set(serializer.validated_data)
        if moving and order.status != Order.Status.PENDING:
            raise Conflict("No se puede cambiar la ubicación de un pedido que ya está en una ruta.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status != Order.Status.PENDING:
            raise Conflict("No se puede borrar un pedido que ya está en una ruta.")
        instance.delete()


class DriverViewSet(BusinessScopedMixin, viewsets.ModelViewSet):
    queryset = Driver.objects.all()
    serializer_class = DriverSerializer

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise Conflict("No se puede borrar un repartidor que tiene rutas.") from None
