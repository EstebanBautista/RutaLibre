"""Demo account: lets anyone try the app without registering.

The demo user has no usable password; the only way in is the public
"demo login" endpoint. Because every visitor shares this account, its data
can be restored to the original state at any time with reset_demo().
"""

from django.contrib.auth import get_user_model
from django.db import transaction

from core.models import Business, Driver, Order, Route

DEMO_USERNAME = "demo"
DEMO_BUSINESS_NAME = "Panadería La Espiga"
DEMO_DEPOT = (3.4516, -76.5320)  # downtown Cali

DEMO_DRIVERS = [
    ("Camila Ríos", "300 555 0101"),
    ("Andrés Valencia", "300 555 0102"),
    ("Luisa Mosquera", "300 555 0103"),
]

# (customer, address, lat, lng, notes). Listed in a deliberately scattered
# order so the un-optimized route zigzags across the city.
DEMO_ORDERS = [
    ("Café San Antonio", "Cra. 10 # 1-45, San Antonio", 3.4480, -76.5410, "Entregar antes de las 8 a. m."),
    ("Colegio Los Andes", "Cl. 18 # 122-30, Pance", 3.3300, -76.5400, ""),
    ("Restaurante Granada", "Av. 9N # 12N-28, Granada", 3.4590, -76.5330, "Preguntar por Marta"),
    ("Tienda El Ingenio", "Cra. 85 # 14-50, El Ingenio", 3.3830, -76.5330, ""),
    ("Hotel El Peñón", "Cra. 3 Oeste # 1-20, El Peñón", 3.4520, -76.5420, "Recepción 24 horas"),
    ("Clínica Santa Mónica", "Av. 6N # 28N-10, Santa Mónica", 3.4700, -76.5330, "Cafetería, segundo piso"),
    ("Panadería Ciudad Jardín", "Cl. 15 # 105-20, Ciudad Jardín", 3.3640, -76.5370, ""),
    ("Oficinas Versalles", "Av. 5N # 21N-40, Versalles", 3.4640, -76.5290, "Piso 4, oficina 402"),
    ("Cafetería Tequendama", "Cl. 5 # 42-15, Tequendama", 3.4130, -76.5450, ""),
    ("Mercado Alameda", "Cl. 8 # 26-10, Alameda", 3.4390, -76.5330, "Puesto 14"),
    ("Consultorio San Fernando", "Cl. 5B # 27-30, San Fernando", 3.4300, -76.5440, ""),
    ("Librería Centenario", "Av. 4N # 4N-30, Centenario", 3.4560, -76.5390, "Timbre dañado, llamar"),
]


def _create_data(business: Business) -> None:
    Driver.objects.bulk_create(
        Driver(business=business, name=name, phone=phone) for name, phone in DEMO_DRIVERS
    )
    # Created one by one (not bulk) so created_at follows the list order.
    for customer, address, lat, lng, notes in DEMO_ORDERS:
        Order.objects.create(
            business=business, customer_name=customer, address=address, lat=lat, lng=lng, notes=notes
        )


@transaction.atomic
def ensure_demo():
    """Returns the demo user, creating the user, business and data if missing."""
    User = get_user_model()
    user, created = User.objects.get_or_create(username=DEMO_USERNAME)
    if created:
        user.set_unusable_password()
        user.save()
    business, business_created = Business.objects.get_or_create(
        owner=user,
        defaults={"name": DEMO_BUSINESS_NAME, "depot_lat": DEMO_DEPOT[0], "depot_lng": DEMO_DEPOT[1]},
    )
    if business_created:
        _create_data(business)
    return user


@transaction.atomic
def reset_demo() -> None:
    """Puts the demo business back to its original data."""
    user = ensure_demo()
    # Lock the business row so two simultaneous resets cannot interleave.
    business = Business.objects.select_for_update().get(owner=user)
    # Routes first: Route protects its driver from deletion.
    Route.objects.filter(business=business).delete()
    Order.objects.filter(business=business).delete()
    Driver.objects.filter(business=business).delete()
    business.name = DEMO_BUSINESS_NAME
    business.depot_lat, business.depot_lng = DEMO_DEPOT
    business.save()
    _create_data(business)


def is_demo_user(user) -> bool:
    return user.is_authenticated and user.username == DEMO_USERNAME
