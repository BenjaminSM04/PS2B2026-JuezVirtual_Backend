from django.core.management.base import BaseCommand
from practice.services import reconcile


class Command(BaseCommand):
    help = "Reconcilia logros históricos sin eliminar ni modificar entregas."

    def handle(self, *args, **options):
        reconcile()
        self.stdout.write("Reconciliación histórica completada.")
