from django.core.management.base import BaseCommand

from core.demo import DEMO_USERNAME, ensure_demo


class Command(BaseCommand):
    help = "Crea el usuario demo, su negocio y sus datos si no existen. Se puede ejecutar varias veces."

    def handle(self, *args, **options):
        ensure_demo()
        self.stdout.write(self.style.SUCCESS(f"Datos demo listos (usuario '{DEMO_USERNAME}')."))
