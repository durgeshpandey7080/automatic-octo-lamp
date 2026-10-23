from decimal import Decimal as D
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Salesperson, ManagerProfile, LubeProduct, DebtorTransaction
from .services import (save_shift, create_debtor, save_credit_sale, save_expense,
    save_debtor_payment, save_lube_sale, save_handover, staff_shift_sales)

class LedgerIntegrationTests(TestCase):
    def setUp(self):
        call_command('seed_demo', verbosity=0)
        self.user=get_user_model().objects.create_user('tester')
        self.person=Salesperson.objects.create(name='Test Person')
        self.manager=ManagerProfile.objects.create(name='Test Manager')
        self.date=timezone.localdate()-timedelta(days=1)
        self.shift=save_shift(self.date,1,[dict(salesperson=self.person,opening_litres=D('100'),closing_litres=D('110')) for _ in range(8)],{'PETROL':D('100'),'DIESEL':D('90')})
        self.debtor=create_debtor(dict(name='Test Customer',phone='',address='',active=True,opening_balance=D('100'),opening_date=self.date),self.user)
    def test_integrated_sales_ledger_and_handover(self):
        product=LubeProduct.objects.create(name='Test Oil 1L',unit='BOTTLE',selling_price=D('250'))
        sale=save_lube_sale(dict(product=product,shift=self.shift,salesperson=self.person,quantity=D('2'),unit_price=D('250'),reference='L1'),self.user)
        product.selling_price=D('300');product.save()
        sale.refresh_from_db();self.assertEqual(sale.amount,D('500'))
        summary=staff_shift_sales(self.shift,self.person)
        self.assertEqual(summary['petrol_litres'],D('40'));self.assertEqual(summary['diesel_litres'],D('40'))
        self.assertEqual(summary['amount'],D('8100'))
        save_credit_sale(self.debtor,dict(shift=self.shift,salesperson=self.person,amount=D('600'),reference='C1',notes=''),self.user)
        save_expense(dict(date=self.date,category='OTHER',description='Repair',payee='',voucher='E1',amount=D('100'),source='SHIFT_CASH',shift=self.shift,salesperson=self.person),self.user)
        record=save_handover(self.shift,self.person,dict(submitted_to=self.manager,cash_received=D('7400'),card=D('0'),paytm_business=D('0'),phonepe_business=D('0'),credit_sales=D('9999'),expenses=D('9999'),notes='C1, E1'),self.user)
        self.assertEqual(record.expected_cash,D('7400'));self.assertEqual(record.status,'Balanced')
        self.assertEqual(self.debtor.balance,D('700'))
        save_debtor_payment(self.debtor,dict(date=self.date,amount=D('200'),reference='P1',payment_method='CASH',received_by=self.manager,notes=''),self.user)
        self.assertEqual(self.debtor.balance,D('500'))
        with self.assertRaises(ValidationError):
            save_credit_sale(self.debtor,dict(shift=self.shift,salesperson=self.person,amount=D('1'),reference='C2',notes=''),self.user)
        self.client.force_login(self.user)
        for url in ['/', '/handovers/',f'/handovers/{self.shift.pk}/{self.person.pk}/','/expenses/','/debtors/',f'/debtors/{self.debtor.pk}/','/lubes/']:
            self.assertEqual(self.client.get(url).status_code,200,url)
        self.assertEqual(self.client.get(f'/managers/{self.manager.pk}/').context['total_cash'],D('7600'))
    def test_overpayment_and_duplicate_reference_rejected(self):
        data=dict(date=self.date,amount=D('101'),reference='P1',payment_method='CASH',received_by=self.manager,notes='')
        with self.assertRaises(ValidationError):save_debtor_payment(self.debtor,data,self.user)
        self.assertEqual(DebtorTransaction.objects.count(),1)
        data['amount']=D('10');save_debtor_payment(self.debtor,data,self.user)
        with self.assertRaises(ValidationError):save_debtor_payment(self.debtor,data,self.user)
    def test_station_expenses_do_not_deduct_staff_cash(self):
        save_expense(dict(date=self.date,category='OTHER',description='Supplies',payee='',voucher='E1',amount=D('100'),source='BANK',shift=None,salesperson=None),self.user)
        self.client.force_login(self.user)
        response=self.client.get(f'/handovers/{self.shift.pk}/{self.person.pk}/')
        self.assertEqual(response.context['form'].instance.expenses,D('0'))
        self.assertTrue(response.context['form'].fields['expenses'].disabled)
    def test_new_forms_and_brand(self):
        self.client.force_login(self.user)
        for url in ['/expenses/add/','/debtors/add/','/credit-sales/add/',f'/debtors/{self.debtor.pk}/repayment/','/lubes/products/add/','/lubes/sales/add/']:
            self.assertContains(self.client.get(url),'Pandey')

    def test_salary_shortage_is_deducted_once(self):
        from .services import save_salary
        from .models import SalaryDeduction, SalaryRecord
        handover = save_handover(self.shift, self.person, dict(submitted_to=self.manager,
            cash_received=D('7500'), card=D('0'), paytm_business=D('0'), phonepe_business=D('0'),
            notes='Short by 100'), self.user)
        month = self.date.replace(day=1)
        with self.assertRaises(ValidationError):
            save_salary(self.person, month, D('50'), self.user)
        self.assertEqual(SalaryRecord.objects.count(), 0)
        salary = save_salary(self.person, month, D('12000'), self.user)
        self.assertEqual(salary.shortage_deduction, D('100'))
        self.assertEqual(salary.net_salary, D('11900'))
        self.assertEqual(SalaryDeduction.objects.get().handover, handover)
        with self.assertRaises(ValidationError):
            save_salary(self.person, month, D('12000'), self.user)
        self.assertEqual(SalaryDeduction.objects.count(), 1)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/salaries/').status_code, 403)
        self.user.is_staff=True; self.user.save()
        self.assertContains(self.client.get('/salaries/'), '11900.00')
        self.assertEqual(self.client.get('/salaries/add/').status_code, 200)



class DebtorAdminPermissionTests(TestCase):
    def test_only_superuser_can_delete_debtor_entries(self):
        from django.contrib import admin
        from django.test import RequestFactory
        model_admin = admin.site._registry[DebtorTransaction]
        request = RequestFactory().get('/admin/')
        request.user = get_user_model().objects.create_user('staff', is_staff=True)
        self.assertFalse(model_admin.has_delete_permission(request))
        request.user.is_superuser = True
        self.assertTrue(model_admin.has_delete_permission(request))
        self.assertIsNone(model_admin.actions)
