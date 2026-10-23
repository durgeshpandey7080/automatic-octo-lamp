from datetime import timedelta
from decimal import Decimal as D
from django.test import TestCase, RequestFactory
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Salesperson, ManagerProfile, Handover, SalaryRecord, SalaryDeduction
from .services import save_shift, save_handover, save_salary

class SalaryRehearsalTests(TestCase):
    def setUp(self):
        call_command('seed_demo',verbosity=0)
        self.owner=get_user_model().objects.create_superuser('salary-owner','','test-only')
        self.person=Salesperson.objects.create(name='DEMO shortage employee')
        self.manager=ManagerProfile.objects.create(name='DEMO manager')
        self.month=timezone.localdate().replace(day=1)
        self.previous=(self.month-timedelta(days=1)).replace(day=1)
        self.shift=save_shift(self.previous,1,[dict(salesperson=self.person,opening_litres=D('100'),closing_litres=D('110')) for _ in range(8)],{'PETROL':D('100'),'DIESEL':D('90')})
        self.values=dict(submitted_to=self.manager,cash_received=D('7500'),card=D('0'),paytm_business=D('0'),phonepe_business=D('0'),notes='DEMO shortage of 100')
        self.handover=save_handover(self.shift,self.person,self.values,self.owner)

    def test_deduction_not_repeated_in_next_month_or_retry(self):
        first=save_salary(self.person,self.previous,D('12000'),self.owner)
        self.assertEqual(first.net_salary,D('11900'))
        with self.assertRaises(ValidationError):
            save_salary(self.person,self.previous,D('12000'),self.owner)
        following=save_salary(self.person,self.month,D('12000'),self.owner)
        self.assertEqual(following.shortage_deduction,D('0'))
        self.assertEqual(following.net_salary,D('12000'))
        self.assertEqual(SalaryDeduction.objects.count(),1)

    def test_unsupported_correction_cannot_overwrite_saved_records_through_ui(self):
        salary=save_salary(self.person,self.previous,D('12000'),self.owner)
        corrected=dict(self.values,cash_received=D('7600'),notes='DEMO correction attempt')
        with self.assertRaises(ValidationError):
            save_handover(self.shift,self.person,corrected,self.owner)
        request=RequestFactory().post('/')
        request.user=self.owner
        for model,obj in [(Handover,self.handover),(SalaryRecord,salary),(SalaryDeduction,SalaryDeduction.objects.get())]:
            model_admin=admin.site._registry[model]
            self.assertFalse(model_admin.has_change_permission(request,obj))
            self.assertFalse(model_admin.has_delete_permission(request,obj))
        self.handover.refresh_from_db();salary.refresh_from_db()
        self.assertEqual(self.handover.cash_received,D('7500'))
        self.assertEqual(salary.net_salary,D('11900'))
        self.assertEqual(SalaryDeduction.objects.count(),1)
