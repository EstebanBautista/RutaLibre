from rest_framework import serializers

from core.demo import is_demo_user
from core.models import Business


class BusinessSerializer(serializers.ModelSerializer):
    is_demo = serializers.SerializerMethodField()

    class Meta:
        model = Business
        fields = ["id", "name", "depot_lat", "depot_lng", "is_demo"]

    def get_is_demo(self, business: Business) -> bool:
        return is_demo_user(business.owner)
