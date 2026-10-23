from io import StringIO
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from .models import Tank, Shift


@override_settings(PUMP_ENVIRONMENT='test', ALLOW_SYNTHETIC_DATA=True)
class SyntheticLabTests(TestCase):
    def run_lab(self):
        output=StringIO()
        call_command('synthetic_lab', confirm_synthetic=True, stdout=output)
        return output.getvalue()

    def test_rehearsal_and_repeat_preserve_existing_records(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertIn('SYNTHETIC LAB PASS',self.run_lab())
        owner=get_user_model().objects.get(username='synthetic-owner')
        self.assertFalse(owner.has_usable_password())
        self.assertEqual(Shift.objects.count(),2)
        before=(Tank.objects.count(),Shift.objects.count())
        with self.assertRaises(CommandError):self.run_lab()
        self.assertEqual(before,(Tank.objects.count(),Shift.objects.count()))

    def test_no_confirmation_or_disabled_flag_is_rejected_without_writes(self):
        with self.assertRaises(CommandError):call_command('synthetic_lab',stdout=StringIO())
        with override_settings(ALLOW_SYNTHETIC_DATA=False):
            with self.assertRaises(CommandError):self.run_lab()
        self.assertFalse(get_user_model().objects.exists())
        self.assertFalse(Tank.objects.exists())

    @override_settings(PUMP_ENVIRONMENT='production')
    def test_production_refuses_all_demo_commands(self):
        for command,options in [('synthetic_lab',{'confirm_synthetic':True}),('demo_rehearsal',{'confirm_demo':True}),('seed_demo',{})]:
            with self.assertRaises(CommandError):call_command(command,stdout=StringIO(),**options)
        self.assertFalse(Tank.objects.exists())

    @override_settings(PUMP_ENVIRONMENT='local')
    def test_explicit_flag_alone_cannot_seed_the_local_station(self):
        with self.assertRaises(CommandError):self.run_lab()
        self.assertFalse(get_user_model().objects.exists())

    def test_existing_accounts_are_never_repurposed(self):
        user=get_user_model().objects.create_user('existing',password='test-only')
        with self.assertRaises(CommandError):self.run_lab()
        user.refresh_from_db()
        self.assertFalse(user.is_superuser)
        self.assertEqual(get_user_model().objects.count(),1)

    def test_station_database_filename_is_rejected_even_with_opt_in(self):
        with patch('pump.synthetic.connection') as connection:
            connection.settings_dict={'NAME':'/data/db.sqlite3'}
            with self.assertRaises(CommandError):self.run_lab()
        self.assertFalse(get_user_model().objects.exists())

    def test_failure_rolls_back_created_accounts_and_business_rows(self):
        def interrupted(*args,**kwargs):
            Tank.objects.create(name='SYNTHETIC interrupted tank',fuel='PETROL',capacity_litres=20000)
            raise CommandError('Synthetic injected interruption')
        with patch('pump.management.commands.synthetic_lab.call_command',side_effect=interrupted):
            with self.assertRaises(CommandError):self.run_lab()
        self.assertFalse(Tank.objects.exists())
        self.assertFalse(get_user_model().objects.exists())
