import os
from decimal import Decimal
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from pump.synthetic import require_synthetic_database
from pump.owner_dashboard import station_summary


class Command(BaseCommand):
    help = 'Build and verify an empty, explicitly isolated synthetic station. Never resets data.'

    def add_arguments(self, parser):
        parser.add_argument('--confirm-synthetic', action='store_true')

    def handle(self, *args, **options):
        require_synthetic_database()
        if not options['confirm_synthetic']:
            raise CommandError('Pass --confirm-synthetic for a dedicated empty synthetic database.')
        with transaction.atomic():
            if any(model.objects.exists() for model in apps.get_app_config('pump').get_models()):
                raise CommandError('Synthetic lab requires empty pump tables. Existing records were left unchanged.')
            User = get_user_model()
            if User.objects.exists():
                raise CommandError('Synthetic lab requires an empty user table; no existing accounts are modified.')
            password = os.environ.get('PUMP_DEV_OWNER_PASSWORD')
            owner = User.objects.create_superuser('synthetic-owner', password=password)
            call_command('demo_rehearsal', confirm_demo=True, verbosity=0, stdout=self.stdout)
            result = station_summary(timezone.localdate()-timedelta(days=1))
            expected = {'fuel_sales': '15200', 'cash': '15820', 'bank': '898',
                        'petrol_litres': '80', 'diesel_litres': '80', 'debtor_balance': '0'}
            for metric, amount in expected.items():
                if Decimal(result['metrics'][metric]) != Decimal(amount):
                    raise CommandError('Synthetic invariant failed: '+metric)
            if result['close_status'] != 'CLOSED' or not result['complete']:
                raise CommandError('Synthetic day did not complete and close.')
            if len(result['stocks']) != 2 or any(Decimal(t['litres']) != 1020 for t in result['stocks']):
                raise CommandError('Synthetic tank balances did not reconcile.')
            self.stdout.write(self.style.SUCCESS('SYNTHETIC LAB PASS: two shifts, fuel/lubes, credit/recovery, expenses, digital settlement, bank allocation, deposit, stock/dips and locked daily closing.'))
            self.stdout.write('Station: '+settings.STATION_CODE+'. Owner: '+owner.username+'. '+
                              ('Password supplied through private environment.' if password else 'Password login disabled.'))
            self.stdout.write('This is a functional rehearsal, not evidence of production readiness or concurrency safety.')
