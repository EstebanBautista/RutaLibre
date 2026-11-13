from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from core.demo import ensure_demo
from core.permissions import HasBusiness
from core.serializers import BusinessSerializer


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
