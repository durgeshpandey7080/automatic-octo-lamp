from datetime import timedelta
from decimal import Decimal as D
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction, IntegrityError
from django.utils import timezone
from .models import Shift, BusinessDayClose, StaffAccess, AuditEvent, Salesperson, ManagerProfile, Tank, Reading, TankOpening, TankDip, TankQualityObservation
from .day_close import transition, review_data
from .services import save_shift, save_handover


class DailyApprovalTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_superuser('owner', '', 'test-pass')
        self.cashier = User.objects.create_user('cashier')
        self.manager = User.objects.create_user('manager', is_staff=True)
        StaffAccess.objects.create(user=self.manager, role='MANAGER')
        StaffAccess.objects.create(user=self.cashier, role='CASHIER')
        self.date = timezone.localdate() - timedelta(days=1)
        self.shift = Shift.objects.create(date=self.date, number=1)

    def reviewed(self):
        transition(self.date, 'submit', self.cashier)
        return transition(self.date, 'review', self.manager)

    def test_exceptions_need_owner_explanation_and_reopening_is_audited(self):
        self.reviewed()
        with self.assertRaises(ValidationError):
            transition(self.date, 'close', self.manager)
        with self.assertRaises(ValidationError):
            transition(self.date, 'close', self.owner, 'short')
        day = transition(self.date, 'close', self.owner, 'Owner accepts incomplete legacy day for reconciliation')
        self.assertEqual(day.status, 'CLOSED')
        self.assertTrue(day.snapshot['issues'])
        with self.assertRaises(PermissionDenied):
            transition(self.date, 'reopen', self.manager, 'Please reopen this day')
        transition(self.date, 'reopen', self.owner, 'Investigate missing historical shift readings')
        self.assertEqual(BusinessDayClose.objects.get(date=self.date).status, 'DRAFT')
        self.assertEqual(AuditEvent.objects.filter(model_name='pump.BusinessDayClose').count(), 4)

    def test_changed_records_invalidate_review_and_self_review_requires_owner_reason(self):
        transition(self.date, 'submit', self.manager)
        with self.assertRaises(ValidationError):
            transition(self.date, 'review', self.manager)
        Shift.objects.create(date=self.date, number=2)
        with self.assertRaises(ValidationError):
            transition(self.date, 'review', self.owner, 'Owner review')
        transition(self.date, 'submit', self.owner)
        with self.assertRaises(ValidationError):
            transition(self.date, 'review', self.owner)
        self.assertEqual(transition(self.date, 'review', self.owner, 'Owner-only office self review').status, 'REVIEWED')

    def test_database_locks_bulk_updates_deletes_and_earlier_inserts(self):
        self.reviewed()
        transition(self.date, 'close', self.owner, 'Owner acknowledges the unresolved exception list')
        with self.assertRaises(ValidationError):
            Shift.objects.create(date=self.date - timedelta(days=1), number=1)
        for action in [lambda: Shift.objects.filter(pk=self.shift.pk).update(number=2),
                       lambda: Shift.objects.filter(pk=self.shift.pk)._raw_delete('default'),
                       lambda: Shift.objects.bulk_create([Shift(date=self.date - timedelta(days=1), number=2)])]:
            with self.assertRaises(IntegrityError), transaction.atomic():
                action()
        Shift.objects.create(date=self.date + timedelta(days=1), number=1)
        transition(self.date, 'reopen', self.owner, 'Correct historical meter assignment details')
        self.assertEqual(Shift.objects.filter(pk=self.shift.pk).update(number=2), 1)

    def test_station_roles_block_direct_urls_and_owner_only_access_assignment(self):
        self.client.force_login(self.cashier)
        self.assertEqual(self.client.get('/staff-access/').status_code, 403)
        self.assertEqual(self.client.get('/admin/').status_code, 403)
        self.assertEqual(self.client.get('/salaries/').status_code, 403)
        self.assertEqual(self.client.post('/operations/income/add/').status_code, 403)
        self.assertEqual(self.client.post('/day-close/', {'date': self.date, 'action': 'review'}).status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post('/staff-access/', {'user': self.cashier.pk, 'role': 'VIEWER', 'active': 'on'}).status_code, 302)
        self.client.force_login(self.cashier)
        self.assertEqual(self.client.post('/day-close/', {'date': self.date, 'action': 'submit'}).status_code, 403)
        self.assertEqual(self.client.get('/day-close/', {'date': self.date}).status_code, 200)


class CompleteDayTests(TestCase):
    def test_manager_can_close_complete_day_without_exception_override(self):
        call_command('seed_demo', verbosity=0)
        owner = get_user_model().objects.create_superuser('owner2', '', 'test-pass')
        manager = get_user_model().objects.create_user('reviewer', is_staff=True)
        StaffAccess.objects.create(user=manager, role='MANAGER')
        person = Salesperson.objects.create(name='Close salesperson')
        receiver = ManagerProfile.objects.create(name='Close manager')
        date = timezone.localdate() - timedelta(days=1)
        for tank in Tank.objects.all():
            TankOpening.objects.create(tank=tank, date=date, litres=D('1000'), recorded_by=owner)
            from datetime import datetime, time
            TankQualityObservation.objects.create(tank=tank,date=date,kind='MORNING',observed_at=timezone.make_aware(datetime.combine(date,time(9))),observed_density=D('740'),temperature_c=D('25'),density_15c=D('742'),correction_source='Test calibrated instrument',water_mm=D('0'),recorded_by=owner)
        for number in [1, 2]:
            shift = save_shift(date, number, [dict(salesperson=person, opening_litres=D(100 + (number-1)*10), closing_litres=D(100 + number*10)) for _ in range(8)], {'PETROL': D('100'), 'DIESEL': D('90')})
            save_handover(shift, person, dict(submitted_to=receiver, cash_received=D('7600'), card=D('0'), paytm_business=D('0'), phonepe_business=D('0'), notes=''), owner)
        for tank in Tank.objects.all():
            TankDip.objects.create(tank=tank, shift=shift, physical_litres=D('920'), expected_litres=D('920'), recorded_by=owner)
        self.assertEqual(review_data(date)[1], [])
        transition(date, 'submit', owner)
        transition(date, 'review', manager)
        self.assertEqual(transition(date, 'close', manager).status, 'CLOSED')
        with self.assertRaises(ValidationError):
            Reading.objects.filter(shift=shift).first().save()
