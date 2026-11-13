from django.contrib import admin

from core.models import Business, Driver, Order, Route, RouteStop


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "depot_lat", "depot_lng")
    search_fields = ("name", "owner__username")


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "business")
    list_filter = ("business",)
    search_fields = ("name",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("customer_name", "address", "status", "business", "created_at")
    list_filter = ("status", "business")
    search_fields = ("customer_name", "address")


class RouteStopInline(admin.TabularInline):
    model = RouteStop
    extra = 0
    readonly_fields = ("order", "sequence", "delivered_at")


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ("id", "date", "driver", "status", "total_km", "naive_km", "business")
    list_filter = ("status", "business", "date")
    inlines = [RouteStopInline]
