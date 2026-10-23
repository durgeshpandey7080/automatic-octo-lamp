from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from pump.models import Tank, Nozzle, Shift
class Command(BaseCommand):
    help = 'Create demo tanks and nozzles only in an empty installation.'
    @transaction.atomic
    def handle(self, *args, **options):
        if Tank.objects.exists() or Nozzle.objects.exists() or Shift.objects.exists():
            raise CommandError('Database is not empty; existing configuration was left unchanged.')
        petrol = Tank.objects.create(name='DEMO Petrol Tank', fuel='PETROL', capacity_litres=20000)
        diesel = Tank.objects.create(name='DEMO Diesel Tank', fuel='DIESEL', capacity_litres=20000)
        for number in range(1, 9):
            Nozzle.objects.create(number=number, tank=petrol if number <= 4 else diesel)
        self.stdout.write(self.style.SUCCESS('Created DEMO configuration. Adjust tanks and nozzle mappings in admin before readings.'))
