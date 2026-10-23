from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models import F
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from .models import Shift, Reading, Salesperson, ManagerProfile, Handover, Debtor, DebtorTransaction, Expense
from .services import save_shift, save_handover


class HandoverTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo', verbosity=0)
        cls.user = get_user_model().objects.create_user('collector', password='test-password-327')
        cls.person = Salesperson.objects.create(name='Test Salesperson')
        cls.other = Salesperson.objects.create(name='Unassigned Person')
        cls.manager = ManagerProfile.objects.create(name='Test Manager')
        cls.shift = save_shift(timezone.localdate() - timedelta(days=2), 1,
            [{'salesperson': cls.person, 'opening_litres': Decimal('100'), 'closing_litres': Decimal('110')}
                for _ in range(8)], {'PETROL': Decimal('100'), 'DIESEL': Decimal('90')})

    def linked_records(self):
        debtor = Debtor.objects.create(name='Test Debtor')
        DebtorTransaction.objects.create(debtor=debtor, kind='SALE', date=self.shift.date,
            shift=self.shift, salesperson=self.person, amount=Decimal('500'), reference='TEST-CREDIT', recorded_by=self.user)
        Expense.objects.create(date=self.shift.date, category='OTHER', description='Test expense',
            voucher='TEST-EXPENSE', amount=Decimal('100'), source='SHIFT_CASH', shift=self.shift,
            salesperson=self.person, recorded_by=self.user)

    def values(self, **changes):
        data = {'submitted_to': self.manager, 'cash_received': Decimal('5000.00'), 'card': Decimal('1000'),
            'paytm_business': Decimal('400'), 'phonepe_business': Decimal('600'), 'credit_sales': Decimal('500'), 'expenses': Decimal('100'),
            'notes': 'Credit slips C1-C3; expense voucher E1.'}
        data.update(changes)
        return data

    def payload(self, **changes):
        data = self.values(**changes)
        return {name: str(value.pk if name == 'submitted_to' else value) for name, value in data.items()}

    def detail_url(self, person=None):
        return reverse('handover_detail', args=[self.shift.pk, (person or self.person).pk])

    def test_balanced_cash_and_manager_totals(self):
        self.linked_records()
        handover = save_handover(self.shift, self.person, self.values(), self.user)
        self.assertEqual(handover.expected_sales, Decimal('7600.00'))
        self.assertEqual(handover.expected_cash, Decimal('5000.00'))
        self.assertEqual(handover.variance, Decimal('0.00'))
        self.assertEqual(handover.status, 'Balanced')
        self.assertEqual(handover.total_collections, Decimal('7000.00'))
        self.assertEqual(handover.paytm_business, Decimal('400.00'))
        self.assertEqual(handover.phonepe_business, Decimal('600.00'))
        self.assertEqual(handover.total_upi, Decimal('1000.00'))
        self.assertEqual(handover.upi, Decimal('0.00'))
        self.assertEqual(handover.submitted_to, self.manager)
        self.assertEqual(handover.recorded_by, self.user)
        self.client.force_login(self.user)
        response = self.client.get(reverse('manager_detail', args=[self.manager.pk]))
        self.assertEqual(response.context['total_cash'], Decimal('5000.00'))
        self.assertEqual(response.context['receipt_count'], 1)
        self.assertContains(response, 'Test Salesperson')

    def test_shortage_and_excess(self):
        shortage = Handover(expected_sales=Decimal('7600'), **self.values(cash_received=Decimal('4900')))
        excess = Handover(expected_sales=Decimal('7600'), **self.values(cash_received=Decimal('5100')))
        self.assertEqual(shortage.status, 'Shortage')
        self.assertEqual(shortage.variance, Decimal('-100.00'))
        self.assertEqual(excess.status, 'Excess')
        self.assertEqual(excess.difference_amount, Decimal('100.00'))

    def test_no_notes_for_balanced_cash_only(self):
        values = self.values(cash_received=Decimal('7600'), card=Decimal('0'), paytm_business=Decimal('0'), phonepe_business=Decimal('0'),
            credit_sales=Decimal('0'), expenses=Decimal('0'), notes='')
        self.assertEqual(save_handover(self.shift, self.person, values, self.user).status, 'Balanced')

    def test_notes_required_for_adjustments_or_variance(self):
        self.client.force_login(self.user)
        response = self.client.post(self.detail_url(), self.payload(notes='   '))
        self.assertContains(response, 'Add credit/expense references')
        self.assertFalse(Handover.objects.exists())
        response = self.client.post(self.detail_url(), self.payload(cash_received=Decimal('7000'),
            card=Decimal('0'), paytm_business=Decimal('0'), phonepe_business=Decimal('0'), credit_sales=Decimal('0'), expenses=Decimal('0'), notes=''))
        self.assertContains(response, 'Add credit/expense references')
        self.assertFalse(Handover.objects.exists())

    def test_adjustments_cannot_exceed_sales(self):
        with self.assertRaises(ValidationError):
            save_handover(self.shift, self.person, self.values(card=Decimal('9000')), self.user)
        self.assertFalse(Handover.objects.exists())

    def test_duplicate_is_rejected_and_existing_receipt_unchanged(self):
        record = save_handover(self.shift, self.person, self.values(), self.user)
        with self.assertRaises(ValidationError):
            save_handover(self.shift, self.person, self.values(cash_received=Decimal('1')), self.user)
        self.client.force_login(self.user)
        self.assertRedirects(self.client.post(self.detail_url(), self.payload(cash_received=Decimal('1'))), self.detail_url())
        record.refresh_from_db()
        self.assertEqual(record.cash_received, Decimal('5000.00'))
        self.assertEqual(Handover.objects.count(), 1)

    def test_server_ignores_posted_sales_and_recorder(self):
        self.client.force_login(self.user)
        data = self.payload()
        data.update(expected_sales='0.01', recorded_by='999999', shift='999999', upi='999999')
        self.assertRedirects(self.client.post(self.detail_url(), data), self.detail_url())
        record = Handover.objects.get()
        self.assertEqual(record.expected_sales, Decimal('7600.00'))
        self.assertEqual(record.recorded_by, self.user)
        self.assertEqual(record.shift, self.shift)
        self.assertEqual(record.upi, Decimal('0.00'))

    def test_negative_nonfinite_and_precision_inputs(self):
        self.client.force_login(self.user)
        for value in ['-1', '1.001', 'NaN', 'Infinity', 'not-money', '']:
            self.client.post(self.detail_url(), self.payload(cash_received=value))
            self.assertFalse(Handover.objects.exists())

    def test_unassigned_person_incomplete_and_unpriced_shift(self):
        with self.assertRaises(ValidationError):
            save_handover(self.shift, self.other, self.values(), self.user)
        Reading.objects.filter(pk=self.shift.readings.first().pk).update(unit_price=None)
        with self.assertRaises(ValidationError):
            save_handover(self.shift, self.person, self.values(), self.user)
        self.shift.readings.first().delete()
        with self.assertRaises(ValidationError):
            save_handover(self.shift, self.person, self.values(), self.user)
        self.assertFalse(Handover.objects.exists())

    def test_inactive_managers_cannot_receive_new_cash(self):
        self.manager.active = False
        self.manager.save()
        self.client.force_login(self.user)
        response = self.client.post(self.detail_url(), self.payload())
        self.assertContains(response, 'Select a valid choice')
        with self.assertRaises(ValidationError):
            save_handover(self.shift, self.person, self.values(), self.user)
        self.assertFalse(Handover.objects.exists())

    def test_departed_salesperson_can_handover_previous_shift(self):
        self.person.active = False
        self.person.save()
        self.assertEqual(save_handover(self.shift, self.person, self.values(), self.user).salesperson, self.person)

    def test_login_csrf_and_manager_profile_permissions(self):
        for url in [reverse('handovers'), self.detail_url(), reverse('managers'),
                    reverse('manager_detail', args=[self.manager.pk])]:
            self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('manager_add')).status_code, 403)
        self.assertEqual(self.client.post(reverse('manager_edit', args=[self.manager.pk]), {'name': 'Changed'}).status_code, 403)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        self.assertEqual(strict.post(self.detail_url(), self.payload()).status_code, 403)

    def test_create_and_edit_manager_profile(self):
        self.user.is_superuser = self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)
        response = self.client.post(reverse('manager_add'), {'name': 'New Manager', 'phone': '12345', 'notes': '', 'active': 'on'})
        profile = ManagerProfile.objects.get(name='New Manager')
        self.assertRedirects(response, reverse('manager_detail', args=[profile.pk]))
        response = self.client.post(reverse('manager_edit', args=[profile.pk]),
            {'name': 'New Manager', 'phone': '54321', 'notes': 'Shift manager'})
        self.assertEqual(response.status_code, 302)
        profile.refresh_from_db()
        self.assertFalse(profile.active)
        self.assertEqual(profile.phone, '54321')

    def test_list_filters_and_saved_receipt(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('handovers')), 'Record handover')
        self.assertEqual(self.client.get(reverse('handovers'), {'shift': 'bad-id'}).status_code, 200)
        self.assertContains(self.client.get(reverse('managers')), 'Test Manager')
        self.assertRedirects(self.client.post(self.detail_url(), self.payload()), self.detail_url())
        receipt = self.client.get(self.detail_url())
        self.assertContains(receipt, 'Cash submission receipt')
        self.assertContains(receipt, 'Test Manager')
        self.assertNotContains(receipt, 'id_cash_received')
        self.assertContains(self.client.get(reverse('handovers')), 'View receipt')

    def test_database_constraints(self):
        record = save_handover(self.shift, self.person, self.values(), self.user)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Handover.objects.filter(pk=record.pk).update(cash_received=-1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Handover.objects.filter(pk=record.pk).update(card=999999)

    def test_empty_installation_pages(self):
        self.shift.readings.all().delete()
        self.shift.delete()
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('handovers')), 'No handovers to record yet')
        self.assertContains(self.client.get(reverse('manager_detail', args=[self.manager.pk])), 'No cash submissions yet')

    def test_exact_paise_boundary_in_sqlite(self):
        # 0.10 + 0.20 must not be rejected by SQLite's floating point check arithmetic.
        self.shift.readings.update(closing_litres=F('opening_litres'))
        Reading.objects.filter(pk=self.shift.readings.first().pk).update(closing_litres=Decimal('110'), unit_price=Decimal('0.030'))
        handover = save_handover(self.shift, self.person, self.values(cash_received=Decimal('0'),
            card=Decimal('0.10'), paytm_business=Decimal('0.00'), phonepe_business=Decimal('0.20'), credit_sales=Decimal('0'), expenses=Decimal('0'), notes=''), self.user)
        self.assertEqual(handover.expected_sales, Decimal('0.30'))
        self.assertEqual(handover.status, 'Balanced')

    def test_legacy_upi_is_preserved_without_assigning_a_provider(self):
        self.linked_records()
        saved = save_handover(self.shift, self.person, self.values(), self.user)
        Handover.objects.filter(pk=saved.pk).update(upi=Decimal('1000'), paytm_business=0, phonepe_business=0)
        saved.refresh_from_db()
        self.assertEqual(saved.total_upi, Decimal('1000.00'))
        self.assertEqual(saved.expected_cash, Decimal('5000.00'))
        self.assertEqual(saved.status, 'Balanced')
        self.client.force_login(self.user)
        self.assertContains(self.client.get(self.detail_url()), 'Earlier UPI (provider not recorded)')

    def test_business_upi_fields_and_saved_receipt(self):
        self.client.force_login(self.user)
        response = self.client.get(self.detail_url())
        self.assertContains(response, 'Paytm for Business (₹)')
        self.assertContains(response, 'PhonePe Business (₹)')
        self.assertNotContains(response, 'name="upi"')
        self.assertRedirects(self.client.post(self.detail_url(), self.payload()), self.detail_url())
        receipt = self.client.get(self.detail_url())
        self.assertContains(receipt, 'Paytm for Business')
        self.assertContains(receipt, 'PhonePe Business')
        self.assertContains(receipt, 'Total UPI collections')
        self.assertNotContains(receipt, 'Earlier UPI (provider not recorded)')

    def test_invalid_business_upi_and_database_limits(self):
        self.client.force_login(self.user)
        for field in ['paytm_business', 'phonepe_business']:
            for value in ['-1', '0.001', 'NaN', 'Infinity', '', '9000']:
                self.client.post(self.detail_url(), self.payload(**{field: value}))
                self.assertFalse(Handover.objects.exists())
        saved = save_handover(self.shift, self.person, self.values(), self.user)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Handover.objects.filter(pk=saved.pk).update(paytm_business=-1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Handover.objects.filter(pk=saved.pk).update(phonepe_business=999999)
