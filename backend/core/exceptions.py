from rest_framework import status
from rest_framework.exceptions import APIException


class Conflict(APIException):
    """The request is valid but clashes with the current state of the record."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "La operación no es posible en el estado actual."
    default_code = "conflict"


class BadRequest(APIException):
    """A 400 whose body is {"detail": "<message>"}, for errors not tied to one field."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Solicitud inválida."
    default_code = "bad_request"


class OptimizerDown(APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "El servicio de optimización no está disponible. Intenta de nuevo en unos segundos."
    default_code = "optimizer_unavailable"


class PhotosDisabled(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Las fotos de evidencia no están configuradas en este servidor."
    default_code = "photos_disabled"


class StorageDown(APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "El almacenamiento de fotos no responde. La entrega no se ve afectada; intenta de nuevo."
    default_code = "storage_unavailable"


class TooManyUploads(APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Se subieron demasiadas fotos en poco tiempo. Espera un momento e intenta de nuevo."
    default_code = "too_many_uploads"
