import uuid
from decimal import Decimal as D
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from .models import *
from .advances import record_advance,apply_advance,reverse_advance
from .payroll import record_payment
from .salary_adjustments import adjust_shortage
from .money_book import statement

class AdvanceTests(TestCase):
    def setUp(self):
        self.owner=get_user_model().objects.create_superuser('owner','','test-only')
        self.other=get_user_model().objects.create_user('staff',is_staff=True)
        self.day=timezone.localdate();self.month=self.day.replace(day=1)
        self.person=Salesperson.objects.create(name='Employee')
        self.salary=SalaryRecord.objects.create(salesperson=self.person,month=self.month,base_salary=D('12000'),shortage_deduction=0,recorded_by=self.owner)
        self.cash=MoneyAccount.objects.create(name='Cash',kind='CASH',opening_date=self.day,opening_balance=D('15000'),recorded_by=self.owner)
        self.bank=MoneyAccount.objects.create(name='Bank',kind='BANK',opening_date=self.day,opening_balance=D('20000'),recorded_by=self.owner)

    def advance(self,amount='1000',account=None,token=None,ref=''):
        return record_advance(self.person.pk,(account or self.cash).pk,self.day,D(amount),ref,'DEMO advance already paid',token or uuid.uuid4(),self.owner)

    def apply(self,a,amount='1000',salary=None,token=None):
        return apply_advance(a.pk,(salary or self.salary).pk,self.day,D(amount),'DEMO approved salary clearing',token or uuid.uuid4(),self.owner)

    def test_partial_cross_month_clearing_and_no_second_outflow(self):
        a=self.advance();token=uuid.uuid4()
        older=SalaryRecord.objects.create(salesperson=self.person,month=self.month-timedelta(days=1),base_salary=12000,shortage_deduction=0,recorded_by=self.owner)
        older.month=older.month.replace(day=1);older.save()
        recovery=self.apply(a,'600',older,token)
        self.assertEqual(self.apply(a,'600',older,token).pk,recovery.pk)
        self.apply(a,'400')
        self.assertEqual(a.remaining_amount,D('0'))
        self.assertEqual(older.outstanding_salary,D('11400'))
        self.assertEqual(self.salary.outstanding_salary,D('11600'))
        self.assertEqual(statement(self.cash,self.day,self.day)['balance'],D('14000'))
        with self.assertRaises(ValidationError):self.apply(a,'1')
        self.assertEqual(AdvanceRecovery.objects.count(),2)

    def test_duplicate_references_bank_and_payment_interaction(self):
        token=uuid.uuid4();a=self.advance(account=self.bank,token=token,ref='BANK-REF')
        self.assertEqual(self.advance(account=self.bank,token=token,ref='BANK-REF').pk,a.pk)
        with self.assertRaises(ValidationError):self.advance(account=self.bank,ref='BANK-REF')
        with self.assertRaises(ValidationError):record_payment(self.salary.pk,self.bank.pk,self.day,D('1'),'BANK-REF','Duplicate reference payment',uuid.uuid4(),self.owner)
        self.apply(a)
        record_payment(self.salary.pk,self.cash.pk,self.day,D('11000'),'','Remaining salary already paid',uuid.uuid4(),self.owner)
        self.assertEqual(self.salary.outstanding_salary,D('0'))
        self.assertEqual(statement(self.bank,self.day,self.day)['balance'],D('19000'))
        self.assertEqual(statement(self.cash,self.day,self.day)['balance'],D('4000'))

    def test_reversal_order_and_salary_release_without_extra_cash(self):
        a=self.advance();r=self.apply(a,'600')
        with self.assertRaises(ValidationError):reverse_advance('advance',a.pk,'Reverse advance while linked',self.owner)
        reverse_advance('recovery',r.pk,'Correct wrong salary clearing',self.owner)
        self.assertEqual(self.salary.outstanding_salary,D('12000'))
        self.assertEqual(statement(self.cash,self.day,self.day)['balance'],D('14000'))
        reverse_advance('advance',a.pk,'Reverse erroneous advance record',self.owner)
        reverse_advance('advance',a.pk,'Retry the same correction',self.owner)
        self.assertEqual(statement(self.cash,self.day,self.day)['balance'],D('15000'))

    def test_bounds_permissions_wrong_employee_and_closed_dates(self):
        for amount in ['0','-1','0.001','16000']:
            with self.assertRaises(ValidationError):self.advance(amount)
        self.assertEqual(SalaryAdvance.objects.count(),0)
        with self.assertRaises(PermissionDenied):record_advance(self.person.pk,self.cash.pk,self.day,D('10'),'','Unauthorized advance attempt',uuid.uuid4(),self.other)
        a=self.advance()
        another=Salesperson.objects.create(name='Other')
        salary=SalaryRecord.objects.create(salesperson=another,month=self.month,base_salary=12000,shortage_deduction=0,recorded_by=self.owner)
        with self.assertRaises(ValidationError):self.apply(a,salary=salary)
        with self.assertRaises(ValidationError):self.apply(a,'1001')
        BusinessDayClose.objects.create(date=self.day,status='CLOSED')
        with self.assertRaises(ValidationError):self.apply(a)
        with self.assertRaises(ValidationError):self.advance()
        with self.assertRaises(ValidationError):reverse_advance('advance',a.pk,'Closed date reversal attempt',self.owner)

    def test_adjusted_salary_cannot_fall_below_applied_advance(self):
        manager=ManagerProfile.objects.create(name='Manager');shift=Shift.objects.create(date=self.day,number=1)
        h=Handover.objects.create(shift=shift,salesperson=self.person,submitted_to=manager,expected_sales=100,cash_received=0,recorded_by=self.owner)
        self.salary.shortage_deduction=D('100');self.salary.save()
        d=SalaryDeduction.objects.create(salary=self.salary,handover=h,amount=100)
        adjust_shortage(d.pk,D('0'),D('100'),uuid.uuid4(),'Waive original shortage',self.owner)
        a=self.advance('12000');self.apply(a,'12000')
        with self.assertRaises(ValidationError):adjust_shortage(d.pk,D('100'),D('0'),uuid.uuid4(),'Restore shortage after full clearing',self.owner)

    def test_pages_owner_post_and_cashier_protection(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get('/salaries/advances/'),'Apply to salary')
        a=self.advance();self.apply(a,'100')
        self.assertContains(self.client.get('/salaries/'),'11900.00')
        self.client.force_login(self.other)
        self.assertEqual(self.client.post('/salaries/advances/',{}).status_code,403)
        StaffAccess.objects.create(user=self.other,role='CASHIER')
        self.assertEqual(self.client.get('/salaries/advances/').status_code,403)
