from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

LATITUDE_VALIDATORS = [MinValueValidator(-90.0), MaxValueValidator(90.0)]
LONGITUDE_VALIDATORS = [MinValueValidator(-180.0), MaxValueValidator(180.0)]


class Business(models.Model):
    """A shop that delivers orders. Every other record belongs to one business."""

    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="business")
    name = models.CharField(max_length=120)
    # The depot is where every route starts and ends.
    depot_lat = models.FloatField(validators=LATITUDE_VALIDATORS)
    depot_lng = models.FloatField(validators=LONGITUDE_VALIDATORS)

    class Meta:
        verbose_name = "negocio"
        verbose_name_plural = "negocios"

    def __str__(self) -> str:
        return self.name


class Driver(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="drivers")
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "repartidor"
        verbose_name_plural = "repartidores"

    def __str__(self) -> str:
        return self.name


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        ASSIGNED = "assigned", "Asignado"
        DELIVERED = "delivered", "Entregado"

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="orders")
    customer_name = models.CharField(max_length=120)
    address = models.CharField(max_length=200)
    lat = models.FloatField(validators=LATITUDE_VALIDATORS)
    lng = models.FloatField(validators=LONGITUDE_VALIDATORS)
    notes = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "pedido"
        verbose_name_plural = "pedidos"

    def __str__(self) -> str:
        return f"{self.customer_name} · {self.address}"


class Route(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planificada"
        IN_PROGRESS = "in_progress", "En curso"
        DONE = "done", "Completada"

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="routes")
    # PROTECT: a driver with routes cannot be deleted by accident.
    driver = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name="routes")
    date = models.DateField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PLANNED)
    total_km = models.FloatField()  # length of the optimized circuit
    naive_km = models.FloatField()  # length visiting the orders as selected
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "ruta"
        verbose_name_plural = "rutas"

    def __str__(self) -> str:
        return f"Ruta {self.pk} · {self.date}"

    @property
    def saved_km(self) -> float:
        return round(self.naive_km - self.total_km, 3)


class RouteStop(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="stops")
    # OneToOne: an order can be on at most one route.
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="stop")
    sequence = models.PositiveIntegerField()  # 1-based position in the route
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(fields=["route", "sequence"], name="unique_sequence_per_route"),
        ]
        verbose_name = "parada"
        verbose_name_plural = "paradas"

    def __str__(self) -> str:
        return f"{self.route_id} #{self.sequence}"
