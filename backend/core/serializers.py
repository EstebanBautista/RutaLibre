from rest_framework import serializers

from core.demo import is_demo_user
from core.models import Business, Driver, Order


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
