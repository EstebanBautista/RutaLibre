from django.db import transaction
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from core.demo import ensure_demo, reset_demo
from core.exceptions import BadRequest, Conflict, OptimizerDown
from core.models import Driver, Order, Route, RouteStop
from core.optimizer_client import OptimizerUnavailable, optimize_route
from core.permissions import HasBusiness, IsDemoUser
from core.serializers import (
    BusinessSerializer,
    DriverSerializer,
    OrderSerializer,
    RouteCreateSerializer,
    RouteDetailSerializer,
    RouteListSerializer,
)

MAX_ORDERS_PER_BUSINESS = 200


@api_view(["POST"])
@permission_classes([AllowAny])
def demo_login(request):
    """Public entry point: returns tokens for the shared demo account."""
    user = ensure_demo()
    refresh = RefreshToken.for_user(user)
    return Response({"access": str(refresh.access_token), "refresh": str(refresh)})


@api_view(["POST"])
@permission_classes([IsDemoUser])
def demo_reset(request):
    reset_demo()
    return Response(status=204)


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


class RouteViewSet(
    BusinessScopedMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    queryset = Route.objects.all()

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("driver", "business")
            .prefetch_related("stops__order")
            .annotate(
                stops_count=Count("stops", distinct=True),
                delivered_count=Count("stops", filter=Q(stops__delivered_at__isnull=False), distinct=True),
            )
            # Explicit: Django drops Meta.ordering on queries that aggregate.
            .order_by("-created_at", "-id")
        )

    def get_serializer_class(self):
        return RouteListSerializer if self.action == "list" else RouteDetailSerializer

    def _detail_response(self, route_id: int, status_code: int = 200) -> Response:
        route = self.get_queryset().get(pk=route_id)
        return Response(RouteDetailSerializer(route).data, status=status_code)

    @staticmethod
    def _pending_orders(business, order_ids):
        return Order.objects.filter(business=business, pk__in=order_ids, status=Order.Status.PENDING)

    def create(self, request):
        """Creates a route: validate, ask the optimizer for the order, then save.

        The optimizer is called *before* opening the transaction so that no
        database lock is held while waiting on the network. The orders are
        checked again inside the transaction, in case another request took
        them in the meantime.
        """
        business = request.user.business
        serializer = RouteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order_ids = serializer.validated_data["order_ids"]
        date = serializer.validated_data.get("date") or timezone.localdate()

        driver = Driver.objects.filter(business=business, pk=serializer.validated_data["driver"]).first()
        if driver is None:
            raise BadRequest("El repartidor no existe.")

        orders_by_id = {order.id: order for order in self._pending_orders(business, order_ids)}
        if len(orders_by_id) != len(order_ids):
            raise BadRequest("Algunos pedidos no existen o ya no están pendientes.")

        # Stops go to the optimizer in the order the user selected them; that
        # order is what "naive_km" measures.
        stops = [
            {"id": order_id, "lat": orders_by_id[order_id].lat, "lng": orders_by_id[order_id].lng}
            for order_id in order_ids
        ]
        token = str(request.auth) if request.auth else ""
        try:
            result = optimize_route((business.depot_lat, business.depot_lng), stops, token)
        except OptimizerUnavailable:
            raise OptimizerDown() from None

        with transaction.atomic():
            locked = list(self._pending_orders(business, order_ids).select_for_update())
            if len(locked) != len(order_ids):
                raise BadRequest("Algunos pedidos no existen o ya no están pendientes.")
            route = Route.objects.create(
                business=business,
                driver=driver,
                date=date,
                total_km=result.optimized_km,
                naive_km=result.naive_km,
            )
            RouteStop.objects.bulk_create(
                RouteStop(route=route, order_id=order_id, sequence=position)
                for position, order_id in enumerate(result.order, start=1)
            )
            Order.objects.filter(pk__in=order_ids).update(status=Order.Status.ASSIGNED)

        return self._detail_response(route.pk, status_code=201)

    @action(detail=True, methods=["post"], url_path=r"stops/(?P<stop_id>\d+)/deliver")
    def deliver(self, request, pk=None, stop_id=None):
        """Marks one stop as delivered. Calling it again changes nothing."""
        route = self.get_object()  # 404 unless the route belongs to this business
        with transaction.atomic():
            stop = get_object_or_404(RouteStop.objects.select_for_update(), pk=stop_id, route=route)
            if stop.delivered_at is None:
                stop.delivered_at = timezone.now()
                stop.save(update_fields=["delivered_at"])
                Order.objects.filter(pk=stop.order_id).update(status=Order.Status.DELIVERED)
                remaining = route.stops.filter(delivered_at__isnull=True).count()
                new_status = Route.Status.DONE if remaining == 0 else Route.Status.IN_PROGRESS
                Route.objects.filter(pk=route.pk).update(status=new_status)
        return self._detail_response(route.pk)
