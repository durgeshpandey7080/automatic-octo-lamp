from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Shift, Reading, Nozzle, Salesperson, DailyFuelPrice
from .services import save_shift as record_shift


def save_shift(date, number, rows, prices=None):
    return record_shift(date, number, rows, prices=prices if prices is not None else {
        'PETROL': Decimal('100.000'), 'DIESEL': Decimal('90.000')})


class LedgerTests(TestCase):
    def setUp(self):
        call_command('seed_demo', verbosity=0)
        self.date = timezone.localdate() - timedelta(days=2)
        self.user = get_user_model().objects.create_user('operator', password='test-password-327')
        self.person = Salesperson.objects.create(name='Test Person')

    def rows(self, opening='100', closing='110'):
        return [dict(salesperson=self.person, opening_litres=Decimal(opening), closing_litres=Decimal(closing)) for _ in range(8)]

    def payload(self, number=1, opening='100', closing='110'):
        data = {'date': str(self.date), 'number': str(number), 'form-TOTAL_FORMS': '8',
                'form-INITIAL_FORMS': '0', 'form-MIN_NUM_FORMS': '8', 'form-MAX_NUM_FORMS': '8',
                'petrol_price': '100.000', 'diesel_price': '90.000'}
        for i, row in enumerate(self.rows(opening, closing)):
            data.update({f'form-{i}-{key}': str(value.pk if key == 'salesperson' else value) for key, value in row.items()})
        return data

    def test_login_required(self):
        self.assertRedirects(self.client.get('/'), '/login/?next=/')

    def test_screen_and_valid_post(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get('/'), 'Save all eight readings')
        response = self.client.post('/', self.payload(), follow=True)
        self.assertContains(response, 'all eight nozzles')
        self.assertEqual(Reading.objects.count(), 8)
        self.assertEqual(Reading.objects.first().litres_sold, Decimal('10'))
        self.assertContains(response, '80.000')

    def test_decreasing_meter_is_rejected_without_writes(self):
        self.client.force_login(self.user)
        response = self.client.post('/', self.payload(opening='110', closing='100'))
        self.assertContains(response, 'Closing must be at least opening')
        self.assertFalse(Shift.objects.exists())

    def test_atomic_rollback_on_last_row(self):
        rows = self.rows()
        rows[-1]['closing_litres'] = Decimal('1')
        with self.assertRaises(ValidationError):
            save_shift(self.date, 1, rows)
        self.assertEqual(Shift.objects.count(), 0)
        self.assertEqual(Reading.objects.count(), 0)
        self.assertEqual(DailyFuelPrice.objects.count(), 0)

    def test_continuity_and_next_business_date(self):
        save_shift(self.date, 1, self.rows())
        with self.assertRaises(ValidationError):
            save_shift(self.date, 2, self.rows())
        save_shift(self.date, 2, self.rows('110', '120'))
        save_shift(self.date + timedelta(days=1), 1, self.rows('120', '130'))
        self.assertEqual(Shift.objects.count(), 3)

    def test_bad_continuity_shown_on_page(self):
        save_shift(self.date, 1, self.rows())
        self.client.force_login(self.user)
        self.assertContains(self.client.post('/', self.payload(number=2)), 'must equal the previous closing')
        self.assertEqual(Shift.objects.count(), 1)

    def test_duplicate_and_skipped_shift(self):
        save_shift(self.date, 1, self.rows())
        for date, number in [(self.date, 1), (self.date + timedelta(days=1), 1)]:
            with self.assertRaises(ValidationError):
                save_shift(date, number, self.rows('110', '120'))

    def test_future_date_and_first_shift_two(self):
        for date, number in [(timezone.localdate() + timedelta(days=1), 1), (self.date, 2)]:
            with self.assertRaises(ValidationError):
                save_shift(date, number, self.rows())

    def test_missing_rows_and_tampered_count(self):
        self.client.force_login(self.user)
        data = self.payload()
        data['form-TOTAL_FORMS'] = '7'
        self.assertContains(self.client.post('/', data), 'at least 8 forms')
        data['form-TOTAL_FORMS'] = '1000'
        self.assertContains(self.client.post('/', data), 'at most 8 forms')
        self.assertFalse(Shift.objects.exists())

    def test_negative_and_precision(self):
        self.client.force_login(self.user)
        for value in ['-1', '0.0001', 'not-a-number']:
            data = self.payload()
            data['form-0-opening_litres'] = value
            self.client.post('/', data)
            self.assertFalse(Shift.objects.exists())

    def test_database_constraints(self):
        save_shift(self.date, 1, self.rows())
        with self.assertRaises(IntegrityError), transaction.atomic():
            Shift.objects.create(date=self.date, number=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Reading.objects.filter(pk=Reading.objects.first().pk).update(closing_litres=-1)

    def test_missing_nozzle_configuration(self):
        Nozzle.objects.first().delete()
        self.client.force_login(self.user)
        self.assertContains(self.client.post('/', self.payload()), 'Configure exactly nozzles')
        self.assertFalse(Shift.objects.exists())

    def test_csrf_protection(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post('/', self.payload()).status_code, 403)

    def test_ledger_admin_is_read_only(self):
        self.user.is_staff = self.user.is_superuser = True
        self.user.save()
        shift = save_shift(self.date, 1, self.rows())
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse('admin:pump_shift_change', args=[shift.pk]), {}).status_code, 403)

    def test_rate_calculation_and_person_grouping(self):
        other = Salesperson.objects.create(name='Second Person')
        rows = self.rows('100.000', '110.250')
        for row in rows[4:]:
            row['salesperson'] = other
        shift = save_shift(self.date, 1, rows, {'PETROL': Decimal('102.375'), 'DIESEL': Decimal('90.000')})
        first = shift.readings.first()
        self.assertEqual(first.litres_sold, Decimal('10.250'))
        self.assertEqual(first.expected_amount, Decimal('1049.34'))
        self.assertIsNone(first.opening_rupees)
        self.assertIsNone(first.closing_rupees)
        self.client.force_login(self.user)
        response = self.client.get('/')
        people = {p['name']: p for p in response.context['people']}
        self.assertEqual(people['Test Person']['amount'], Decimal('4197.36'))
        self.assertEqual(people['Second Person']['amount'], Decimal('3690.00'))
        self.assertEqual(response.context['total_due'], Decimal('7887.36'))

    def test_price_locks_per_day_and_changes_next_day(self):
        first = save_shift(self.date, 1, self.rows())
        with self.assertRaises(ValidationError):
            save_shift(self.date, 2, self.rows('110', '120'), {'PETROL': Decimal('101'), 'DIESEL': Decimal('90')})
        self.assertEqual(Shift.objects.count(), 1)
        save_shift(self.date, 2, self.rows('110', '120'))
        save_shift(self.date + timedelta(days=1), 1, self.rows('120', '130'),
                   {'PETROL': Decimal('101'), 'DIESEL': Decimal('91')})
        self.assertEqual(first.readings.first().unit_price, Decimal('100'))
        self.assertEqual(first.readings.first().expected_amount, Decimal('1000.00'))

    def test_missing_negative_or_invalid_prices(self):
        for prices in [{}, {'PETROL': '-1', 'DIESEL': '90'}, {'PETROL': 'NaN', 'DIESEL': '90'},
                       {'PETROL': '100.0001', 'DIESEL': '90'}]:
            with self.assertRaises(ValidationError):
                save_shift(self.date, 1, self.rows(), prices)
            self.assertFalse(Shift.objects.exists())
            self.assertFalse(DailyFuelPrice.objects.exists())

    def test_salesperson_required_and_active(self):
        rows = self.rows()
        rows[-1]['salesperson'] = None
        with self.assertRaises(ValidationError):
            save_shift(self.date, 1, rows)
        self.person.active = False
        self.person.save()
        self.client.force_login(self.user)
        response = self.client.post('/', self.payload())
        self.assertContains(response, 'Select a valid choice')
        self.assertFalse(Shift.objects.exists())

    def test_half_paise_rounds_up_and_zero_sales(self):
        shift = save_shift(self.date, 1, self.rows('100', '100.005'), {'PETROL': '1', 'DIESEL': '1'})
        self.assertEqual(shift.readings.first().expected_amount, Decimal('0.01'))
        second = save_shift(self.date, 2, self.rows('100.005', '100.005'), {'PETROL': '1', 'DIESEL': '1'})
        self.assertEqual(second.readings.first().expected_amount, Decimal('0.00'))

    def test_older_unpriced_entries_are_explicitly_marked(self):
        shift = Shift.objects.create(date=self.date, number=1)
        row = self.rows()[0]
        row.pop('salesperson')
        Reading.objects.create(shift=shift, nozzle=Nozzle.objects.first(), **row)
        self.client.force_login(self.user)
        response = self.client.get('/')
        self.assertContains(response, 'older readings unpriced')
        self.assertIsNone(Reading.objects.first().expected_amount)

    def test_entry_and_reports_have_no_rupee_meter_fields(self):
        self.client.force_login(self.user)
        response = self.client.get('/')
        self.assertNotContains(response, 'opening_rupees')
        self.assertNotContains(response, 'closing_rupees')
        self.assertNotContains(response, 'RUPEE METER')
        self.assertNotContains(response, 'Rupee-meter sales')
        self.assertEqual(self.client.post('/', self.payload()).status_code, 302)
        self.assertEqual(Reading.objects.count(), 8)
        self.assertFalse(Reading.objects.exclude(opening_rupees=None).exists())
        self.assertEqual(Reading.objects.first().expected_amount, Decimal('1000.00'))

    def test_legacy_rupee_counters_preserved_and_not_required_for_next_shift(self):
        first = save_shift(self.date, 1, self.rows())
        first.readings.update(opening_rupees=Decimal('500000'), closing_rupees=Decimal('501000'))
        second = save_shift(self.date, 2, self.rows('110', '120'))
        legacy = first.readings.first()
        self.assertEqual(legacy.opening_rupees, Decimal('500000'))
        self.assertEqual(legacy.closing_rupees, Decimal('501000'))
        self.assertIsNone(second.readings.first().opening_rupees)
        self.assertEqual(second.readings.first().expected_amount, Decimal('1000.00'))
