import uuid
from datetime import timedelta
from decimal import Decimal as D
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from .models import *
from .shortages import receive,reverse_receipt,collectible
from .services import save_salary
from .salary_adjustments import adjust_shortage
from .money_book import statement
from .payroll import record_payment

class ShortageTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_superuser('owner','','test-only')
        self.staff=get_user_model().objects.create_user('staff',is_staff=True)
        self.day=timezone.localdate();self.month=self.day.replace(day=1)
        self.person=Salesperson.objects.create(name='Employee')
        manager=ManagerProfile.objects.create(name='Manager')
        shift=Shift.objects.create(date=self.day,number=1)
        self.h=Handover.objects.create(shift=shift,salesperson=self.person,submitted_to=manager,expected_sales=100,cash_received=0,recorded_by=self.user)
        self.cash=MoneyAccount.objects.create(name='Cash',kind='CASH',opening_date=self.day,opening_balance=1000,recorded_by=self.user)
        self.bank=MoneyAccount.objects.create(name='Bank',kind='BANK',opening_date=self.day,opening_balance=1000,recorded_by=self.user)
    def receipt(self,amount='40',account=None,token=None,ref=''):
        return receive(self.h.pk,(account or self.cash).pk,self.day,D(amount),ref,'DEMO shortage money received',token or uuid.uuid4(),self.user)
    def salary(self):return save_salary(self.person,self.month,D('12000'),self.user)
    def test_before_payroll_and_after_payroll_no_double_deduction(self):
        first=self.receipt('30');salary=self.salary()
        self.assertEqual(salary.shortage_deduction,D('70'))
        second=self.receipt('70');self.assertEqual(second.salary_id,salary.pk)
        self.assertEqual(salary.adjusted_net_salary,D('12000'))
        self.assertEqual(statement(self.cash,self.day,self.day)['balance'],D('1100'))
        with self.assertRaises(ValidationError):self.receipt('1')
        with self.assertRaises(ValidationError):reverse_receipt(first.pk,'Pre payroll correction attempted',self.user)
        reverse_receipt(second.pk,'Incorrect post payroll receipt',self.user)
        self.assertEqual(salary.adjusted_net_salary,D('11930'))
    def test_waiver_receipt_and_correction_limits(self):
        salary=self.salary();d=salary.deductions.get()
        adjust_shortage(d.pk,D('40'),D('100'),uuid.uuid4(),'DEMO waive sixty rupees',self.user)
        with self.assertRaises(ValidationError):self.receipt('41')
        r=self.receipt();self.assertEqual(salary.adjusted_net_salary,D('12000'))
        with self.assertRaises(ValidationError):adjust_shortage(d.pk,D('0'),D('40'),uuid.uuid4(),'Attempt double credit waiver',self.user)
        record_payment(salary.pk,self.cash.pk,self.day,D('1000'),'','DEMO salary partial payment',uuid.uuid4(),self.user)
        salary.base_salary=D('1000');salary.save()
        with self.assertRaises(ValidationError):reverse_receipt(r.pk,'Would leave salary overpaid',self.user)
    def test_retry_bank_dates_permissions_and_render(self):
        token=uuid.uuid4();r=self.receipt(account=self.bank,token=token,ref='BANK-1')
        self.assertEqual(self.receipt(account=self.bank,token=token,ref='BANK-1').pk,r.pk)
        self.assertEqual(statement(self.bank,self.day,self.day)['balance'],D('1040'))
        with self.assertRaises(ValidationError):self.receipt('20',token=token)
        with self.assertRaises(ValidationError):self.receipt(account=self.bank,ref='BANK-1')
        with self.assertRaises(ValidationError):self.receipt(account=self.bank)
        for a in ['0','-1','0.001','NaN']:
            with self.assertRaises(ValidationError):self.receipt(a)
        with self.assertRaises(PermissionDenied):receive(self.h.pk,self.cash.pk,self.day,D('1'),'','Staff unauthorized receipt',uuid.uuid4(),self.staff)
        with self.assertRaises(ValidationError):receive(self.h.pk,self.cash.pk,self.day+timedelta(days=1),D('1'),'','Future receipt validation',uuid.uuid4(),self.user)
        self.client.force_login(self.user);self.assertContains(self.client.get('/salaries/shortage-recovery/'),'BANK-1')
        self.client.force_login(self.staff);self.assertEqual(self.client.post('/salaries/shortage-recovery/',{}).status_code,403)
    def test_closed_date_and_reversal(self):
        r=self.receipt();reverse_receipt(r.pk,'Incorrect receipt corrected',self.user)
        self.assertEqual(collectible(self.h),D('100'))
        r=self.receipt();BusinessDayClose.objects.create(date=self.day,status='CLOSED')
        with self.assertRaises(ValidationError):self.receipt('1')
        with self.assertRaises(ValidationError):reverse_receipt(r.pk,'Closed date correction attempted',self.user)
    def test_full_recovery_before_payroll(self):
        self.receipt('100');salary=self.salary()
        self.assertEqual(salary.shortage_deduction,0)
        self.assertEqual(salary.adjusted_net_salary,D('12000'))
