import uuid
from datetime import timedelta
from decimal import Decimal as D
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from .models import SalaryRecord,SalaryPayment,Salesperson,MoneyAccount,BusinessDayClose,SalaryDeduction,Handover,Shift,ManagerProfile
from .payroll import record_payment,reverse_payment
from .money_book import statement
from .salary_adjustments import adjust_shortage

class SalaryPaymentTests(TestCase):
    def setUp(self):
        self.owner=get_user_model().objects.create_superuser('owner','','test-only')
        self.staff=get_user_model().objects.create_user('staff',is_staff=True)
        self.day=timezone.localdate()
        self.person=Salesperson.objects.create(name='Test Employee')
        self.salary=SalaryRecord.objects.create(salesperson=self.person,month=self.day.replace(day=1),base_salary=D('12000'),shortage_deduction=D('0'),recorded_by=self.owner)
        self.cash=MoneyAccount.objects.create(name='Cash',kind='CASH',opening_date=self.day,opening_balance=D('15000'),recorded_by=self.owner)
        self.bank=MoneyAccount.objects.create(name='Bank',kind='BANK',opening_date=self.day,opening_balance=D('20000'),recorded_by=self.owner)

    def pay(self,amount='500',account=None,token=None,ref=''):
        return record_payment(self.salary.pk,(account or self.cash).pk,self.day,D(amount),ref,'Test payment already made',token or uuid.uuid4(),self.owner)

    def test_partial_payment_idempotence_bank_and_reversal(self):
        token=uuid.uuid4();p=self.pay(token=token)
        self.assertEqual(self.pay(token=token).pk,p.pk)
        self.assertEqual(self.salary.paid_amount,D('500'))
        self.assertEqual(self.salary.outstanding_salary,D('11500'))
        self.assertEqual(statement(self.cash,self.day,self.day)['balance'],D('14500'))
        bank=self.pay('1000',self.bank,ref='BANK-UTR')
        self.assertEqual(statement(self.bank,self.day,self.day)['balance'],D('19000'))
        reverse_payment(p.pk,'Correct the erroneous payment',self.owner)
        reverse_payment(p.pk,'Repeat correction request',self.owner)
        self.assertEqual(self.salary.paid_amount,D('1000'))
        self.assertEqual(statement(self.cash,self.day,self.day)['balance'],D('15000'))
        self.assertEqual(SalaryPayment.objects.count(),2)

    def test_bounds_references_permissions_and_dates(self):
        for value in ['0','-1','12001','0.001']:
            with self.assertRaises(ValidationError):self.pay(value)
        with self.assertRaises(ValidationError):self.pay(account=self.bank)
        self.pay(account=self.bank,ref='UNIQUE-REF')
        with self.assertRaises(ValidationError):self.pay(account=self.bank,ref='UNIQUE-REF')
        with self.assertRaises(PermissionDenied):record_payment(self.salary.pk,self.cash.pk,self.day,D('1'),'','Unauthorized staff attempt',uuid.uuid4(),self.staff)
        with self.assertRaises(ValidationError):record_payment(self.salary.pk,self.cash.pk,self.day+timedelta(days=1),D('1'),'','Future payment attempt',uuid.uuid4(),self.owner)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(f'/salaries/{self.salary.pk}/payment/').status_code,403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(f'/salaries/{self.salary.pk}/payment/').status_code,200)
        self.assertContains(self.client.get('/salaries/'),'Record payment')

    def test_insufficient_cash_and_closed_period(self):
        self.cash.opening_balance=D('10');self.cash.save()
        with self.assertRaises(ValidationError):self.pay('100')
        self.assertEqual(SalaryPayment.objects.count(),0)
        self.cash.opening_balance=D('15000');self.cash.save()
        p=self.pay()
        BusinessDayClose.objects.create(date=self.day,status='CLOSED')
        with self.assertRaises(ValidationError):self.pay('100')
        with self.assertRaises(ValidationError):reverse_payment(p.pk,'Closed date reversal attempt',self.owner)
        self.assertEqual(SalaryPayment.objects.count(),1)

    def test_adjustment_cannot_reduce_due_below_paid(self):
        manager=ManagerProfile.objects.create(name='Manager')
        shift=Shift.objects.create(date=self.day,number=1)
        handover=Handover.objects.create(shift=shift,salesperson=self.person,submitted_to=manager,expected_sales=D('100'),cash_received=0,recorded_by=self.owner)
        self.salary.shortage_deduction=D('100');self.salary.save()
        deduction=SalaryDeduction.objects.create(salary=self.salary,handover=handover,amount=D('100'))
        adjust_shortage(deduction.pk,D('0'),D('100'),uuid.uuid4(),'Waive shortage for test',self.owner)
        self.pay('12000')
        with self.assertRaises(ValidationError):adjust_shortage(deduction.pk,D('100'),D('0'),uuid.uuid4(),'Restore original shortage after full payment',self.owner)
        self.assertEqual(self.salary.outstanding_salary,D('0'))
