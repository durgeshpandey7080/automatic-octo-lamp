"""Synthetic pilot, isolated by Django's temporary test database."""
from datetime import datetime,time,timedelta
from decimal import Decimal as D
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Tank,Salesperson,ManagerProfile,Debtor,LubeProduct,MoneyAccount,TankQualityObservation,StaffAccess,Reading
from .services import save_shift,save_credit_sale,save_expense,save_lube_sale,save_handover,save_debtor_payment
from .operations import save_operation,lube_stock
from .stock import save_stock_entry,stock_summary
from .money_book import assign_bank,save_transfer,statement
from .payment_imports import preview_csv,commit_import,match_evidence
from .day_close import transition,review_data


class IsolatedPilotTests(TestCase):
    def test_two_shifts_stock_collections_repayment_bank_and_approved_close(self):
        call_command('seed_demo',verbosity=0)
        user=get_user_model().objects.create_superuser('pilot-owner','','pilot-only-password')
        reviewer=get_user_model().objects.create_user('pilot-reviewer',is_staff=True)
        StaffAccess.objects.create(user=reviewer,role='MANAGER')
        person=Salesperson.objects.create(name='PILOT salesperson')
        manager=ManagerProfile.objects.create(name='PILOT manager')
        debtor=Debtor.objects.create(name='PILOT credit customer')
        date=timezone.localdate()-timedelta(days=1)
        observed=timezone.make_aware(datetime.combine(date,time(9)))
        cash=MoneyAccount.objects.create(name='PILOT cash',kind='CASH',opening_date=date,opening_balance=D('1000'),recorded_by=user)
        bank=MoneyAccount.objects.create(name='PILOT bank',kind='BANK',opening_date=date,opening_balance=D('500'),recorded_by=user)
        for tank in Tank.objects.all():
            save_stock_entry('opening',dict(tank=tank,date=date,litres=D('1000')),user)
            delivery=save_stock_entry('delivery',dict(tank=tank,date=date,litres=D('100'),invoice='PILOT-'+tank.fuel,supplier='PILOT supplier'),user)
            for kind,linked in [('MORNING',None),('DELIVERY',delivery)]:
                row=TankQualityObservation(tank=tank,date=date,kind=kind,delivery=linked,observed_at=observed,
                    observed_density=D('740'),temperature_c=D('25'),density_15c=D('742'),
                    correction_source='SYNTHETIC TEST instrument',water_mm=D('0'),recorded_by=user)
                row.full_clean();row.save()
        first=save_shift(date,1,[dict(salesperson=person,opening_litres=D('100'),closing_litres=D('110')) for _ in range(8)],{'PETROL':D('100'),'DIESEL':D('90')})
        product=LubeProduct.objects.create(name='PILOT oil',unit='BOTTLE',selling_price=D('50'))
        save_operation('lube-stock',dict(product=product,date=date,kind='OPENING',quantity=D('5'),unit_cost=D('30')),user)
        save_lube_sale(dict(shift=first,salesperson=person,product=product,quantity=D('2'),unit_price=D('50'),reference=''),user)
        save_credit_sale(debtor,dict(shift=first,salesperson=person,amount=D('100'),reference='',notes='PILOT credit'),user)
        save_expense(dict(date=date,source='SHIFT_CASH',shift=first,salesperson=person,category='OTHER',description='PILOT shift expense',payee='',voucher='',amount=D('50')),user)
        collection=save_operation('collection',dict(shift=first,salesperson=person,method='PAYTM',amount=D('200'),reference='PILOT-TX',terminal='PILOT-MERCHANT'),user)
        save_handover(first,person,dict(submitted_to=manager,cash_received=D('7350'),card=D('0'),paytm_business=D('0'),phonepe_business=D('0'),notes='PILOT exact handover'),user)
        second=save_shift(date,2,[dict(salesperson=person,opening_litres=D('110'),closing_litres=D('120')) for _ in range(8)],{'PETROL':D('100'),'DIESEL':D('90')})
        save_handover(second,person,dict(submitted_to=manager,cash_received=D('7600'),card=D('0'),paytm_business=D('0'),phonepe_business=D('0'),notes='PILOT exact handover'),user)
        save_debtor_payment(debtor,dict(date=date,amount=D('100'),reference='',payment_method='CASH',received_by=manager,notes='PILOT repayment'),user)
        save_expense(dict(date=date,source='STATION_CASH',shift=None,salesperson=None,category='OTHER',description='PILOT station expense',payee='',voucher='',amount=D('30')),user)
        preview=preview_csv(f'reference,date,amount,status,description\nPILOT-TX,{date},200.00,SUCCESS,PILOT\n'.encode())
        batch,_=commit_import(preview,'PAYTM','PILOT-MERCHANT',user)
        match_evidence(batch.paymentevidence_set.get().pk,collection.pk,user)
        settlement=save_operation('bank',dict(collection=collection,settlement_date=date,bank_name='PILOT bank',bank_reference='PILOT-UTR',net_received=D('198'),fee=D('2')),user)
        assign_bank('SETTLEMENT',settlement.pk,bank,user)
        save_transfer(dict(date=date,source=cash,destination=bank,amount=D('200'),external_reference='PILOT-DEPOSIT',notes='PILOT recorded cash deposit'),user)
        for tank in Tank.objects.all():
            self.assertEqual(stock_summary(tank,date)['expected'],D('1020'))
            save_stock_entry('dip',dict(tank=tank,shift=second,physical_litres=D('1020')),user)
        self.assertEqual(debtor.balance,D('0'))
        product.refresh_from_db()
        self.assertEqual(lube_stock(product),D('3'))
        self.assertEqual(statement(cash,date,date)['balance'],D('15820'))
        self.assertEqual(statement(bank,date,date)['balance'],D('898'))
        self.assertEqual(review_data(date)[1],[])
        transition(date,'submit',user)
        transition(date,'review',reviewer)
        self.assertEqual(transition(date,'close',reviewer).status,'CLOSED')
        with self.assertRaises(ValidationError):
            Reading.objects.first().save()

    def test_readiness_is_owner_only_and_never_creates_openings(self):
        owner=get_user_model().objects.create_superuser('readiness-owner','','pilot-only-password')
        ordinary=get_user_model().objects.create_user('readiness-user')
        self.client.force_login(ordinary)
        self.assertEqual(self.client.get('/setup-readiness/').status_code,403)
        self.client.force_login(owner)
        self.assertContains(self.client.get('/setup-readiness/'),'Missing balances are unknown, not zero')
        self.assertEqual(MoneyAccount.objects.count(),0)


class DemoCommandTests(TestCase):
    def test_demo_command_checks_totals_and_refuses_repeat(self):
        from django.core.management.base import CommandError
        from .models import Shift, BusinessDayClose
        get_user_model().objects.create_superuser('demo-owner','','test-only')
        with self.assertRaises(CommandError):
            call_command('demo_rehearsal',verbosity=0)
        self.assertEqual(Shift.objects.count(),0)
        call_command('demo_rehearsal',confirm_demo=True,verbosity=0)
        self.assertEqual(Shift.objects.count(),2)
        self.assertEqual(BusinessDayClose.objects.get().status,'CLOSED')
        with self.assertRaises(CommandError):
            call_command('demo_rehearsal',confirm_demo=True,verbosity=0)
        self.assertEqual(Shift.objects.count(),2)
