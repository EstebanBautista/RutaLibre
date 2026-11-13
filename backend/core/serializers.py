from rest_framework import serializers

from core.demo import is_demo_user
from core.models import Business, Driver, Order, Route, RouteStop


class BusinessSerializer(serializers.ModelSerializer):
    is_demo = serializers.SerializerMethodField()

    class Meta:
        model = Business
        fields = ["id", "name", "depot_lat", "depot_lng", "is_demo"]

    def get_is_demo(self, business: Business) -> bool:
        return is_demo_user(business.owner)


class DriverSerializer(serializers.ModelSerializer):
    class Meta:
        model = Driver
        fields = ["id", "name", "phone"]


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ["id", "customer_name", "address", "lat", "lng", "notes", "status", "created_at"]
        # The status only changes through routes and deliveries, never directly.
        read_only_fields = ["status", "created_at"]


class RouteCreateSerializer(serializers.Serializer):
    """Input for creating a route. Ownership and status checks happen in the view."""

    driver = serializers.IntegerField()
    order_ids = serializers.ListField(
        child=serializers.IntegerField(), min_length=1, max_length=100, allow_empty=False
    )
    date = serializers.DateField(required=False)

    def validate_order_ids(self, order_ids: list[int]) -> list[int]:
        if len(order_ids) != len(set(order_ids)):
            raise serializers.ValidationError("Hay pedidos repetidos.")
        return order_ids


class RouteStopSerializer(serializers.ModelSerializer):
    order = serializers.SerializerMethodField()

    class Meta:
        model = RouteStop
        fields = ["id", "sequence", "delivered_at", "order"]

    def get_order(self, stop: RouteStop) -> dict:
        order = stop.order
        return {
            "id": order.id,
            "customer_name": order.customer_name,
            "address": order.address,
            "notes": order.notes,
            "lat": order.lat,
            "lng": order.lng,
        }


class RouteListSerializer(serializers.ModelSerializer):
    driver = serializers.SerializerMethodField()
    saved_km = serializers.FloatField(read_only=True)
    stops_count = serializers.IntegerField(read_only=True)
    delivered_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Route
        fields = [
            "id",
            "date",
            "status",
            "total_km",
            "naive_km",
            "saved_km",
            "driver",
            "stops_count",
            "delivered_count",
        ]

    def get_driver(self, route: Route) -> dict:
        return {"id": route.driver_id, "name": route.driver.name}


class RouteDetailSerializer(RouteListSerializer):
    depot = serializers.SerializerMethodField()
    stops = RouteStopSerializer(many=True, read_only=True)

    class Meta(RouteListSerializer.Meta):
        fields = [*RouteListSerializer.Meta.fields, "depot", "stops"]

    def get_depot(self, route: Route) -> dict:
        return {"lat": route.business.depot_lat, "lng": route.business.depot_lng}
