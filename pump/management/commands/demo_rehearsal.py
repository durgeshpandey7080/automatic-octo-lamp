from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from datetime import datetime,time,timedelta
from decimal import Decimal as D
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone
from pump.models import Shift,Tank,Salesperson,ManagerProfile,Debtor,LubeProduct,MoneyAccount,TankQualityObservation,StaffAccess,Reading
from pump.services import save_shift,save_credit_sale,save_expense,save_lube_sale,save_handover,save_debtor_payment
from pump.operations import save_operation,lube_stock
from pump.stock import save_stock_entry,stock_summary
from pump.money_book import assign_bank,save_transfer,statement
from pump.payment_imports import preview_csv,commit_import,match_evidence
from pump.day_close import transition,review_data

class Command(BaseCommand):
    help = 'Enter a labelled synthetic business day into an EMPTY demo station only.'

    def add_arguments(self, parser):
        parser.add_argument('--confirm-demo', action='store_true')

    def check_equal(self, actual, expected):
        if actual != expected:
            raise CommandError(f'Demo verification failed: {actual!r} != {expected!r}')

    @transaction.atomic
    def handle(self, *args, **options):
        if settings.PUMP_ENVIRONMENT == 'production':
            raise CommandError('Demo rehearsal is forbidden in production.')
        if not options['confirm_demo']:
            raise CommandError('Pass --confirm-demo only for an empty demonstration station.')
        if Tank.objects.exists() or Shift.objects.exists() or MoneyAccount.objects.exists():
            raise CommandError('Demo rehearsal requires an empty station. No changes made.')
        call_command('seed_demo',verbosity=0)
        user=get_user_model().objects.filter(is_superuser=True,is_active=True).first()
        if not user:
            raise CommandError('An existing owner is required.')
        person=Salesperson.objects.create(name='DEMO salesperson')
        manager=ManagerProfile.objects.create(name='DEMO manager')
        debtor=Debtor.objects.create(name='DEMO credit customer')
        date=timezone.localdate()-timedelta(days=1)
        observed=timezone.make_aware(datetime.combine(date,time(9)))
        cash=MoneyAccount.objects.create(name='DEMO cash',kind='CASH',opening_date=date,opening_balance=D('1000'),recorded_by=user)
        bank=MoneyAccount.objects.create(name='DEMO bank',kind='BANK',opening_date=date,opening_balance=D('500'),recorded_by=user)
        for tank in Tank.objects.all():
            save_stock_entry('opening',dict(tank=tank,date=date,litres=D('1000')),user)
            delivery=save_stock_entry('delivery',dict(tank=tank,date=date,litres=D('100'),invoice='DEMO-'+tank.fuel,supplier='DEMO supplier'),user)
            for kind,linked in [('MORNING',None),('DELIVERY',delivery)]:
                row=TankQualityObservation(tank=tank,date=date,kind=kind,delivery=linked,observed_at=observed,
                    observed_density=D('740'),temperature_c=D('25'),density_15c=D('742'),
                    correction_source='SYNTHETIC TEST instrument',water_mm=D('0'),recorded_by=user)
                row.full_clean();row.save()
        first=save_shift(date,1,[dict(salesperson=person,opening_litres=D('100'),closing_litres=D('110')) for _ in range(8)],{'PETROL':D('100'),'DIESEL':D('90')})
        product=LubeProduct.objects.create(name='DEMO oil',unit='BOTTLE',selling_price=D('50'))
        save_operation('lube-stock',dict(product=product,date=date,kind='OPENING',quantity=D('5'),unit_cost=D('30')),user)
        save_lube_sale(dict(shift=first,salesperson=person,product=product,quantity=D('2'),unit_price=D('50'),reference=''),user)
        save_credit_sale(debtor,dict(shift=first,salesperson=person,amount=D('100'),reference='',notes='DEMO credit'),user)
        save_expense(dict(date=date,source='SHIFT_CASH',shift=first,salesperson=person,category='OTHER',description='DEMO shift expense',payee='',voucher='',amount=D('50')),user)
        collection=save_operation('collection',dict(shift=first,salesperson=person,method='PAYTM',amount=D('200'),reference='DEMO-TX',terminal='DEMO-MERCHANT'),user)
        save_handover(first,person,dict(submitted_to=manager,cash_received=D('7350'),card=D('0'),paytm_business=D('0'),phonepe_business=D('0'),notes='DEMO exact handover'),user)
        second=save_shift(date,2,[dict(salesperson=person,opening_litres=D('110'),closing_litres=D('120')) for _ in range(8)],{'PETROL':D('100'),'DIESEL':D('90')})
        save_handover(second,person,dict(submitted_to=manager,cash_received=D('7600'),card=D('0'),paytm_business=D('0'),phonepe_business=D('0'),notes='DEMO exact handover'),user)
        save_debtor_payment(debtor,dict(date=date,amount=D('100'),reference='',payment_method='CASH',received_by=manager,notes='DEMO repayment'),user)
        save_expense(dict(date=date,source='STATION_CASH',shift=None,salesperson=None,category='OTHER',description='DEMO station expense',payee='',voucher='',amount=D('30')),user)
        preview=preview_csv(f'reference,date,amount,status,description\nDEMO-TX,{date},200.00,SUCCESS,DEMO\n'.encode())
        batch,_=commit_import(preview,'PAYTM','DEMO-MERCHANT',user)
        match_evidence(batch.paymentevidence_set.get().pk,collection.pk,user)
        settlement=save_operation('bank',dict(collection=collection,settlement_date=date,bank_name='DEMO bank',bank_reference='DEMO-UTR',net_received=D('198'),fee=D('2')),user)
        assign_bank('SETTLEMENT',settlement.pk,bank,user)
        save_transfer(dict(date=date,source=cash,destination=bank,amount=D('200'),external_reference='DEMO-DEPOSIT',notes='DEMO recorded cash deposit'),user)
        for tank in Tank.objects.all():
            self.check_equal(stock_summary(tank,date)['expected'],D('1020'))
            save_stock_entry('dip',dict(tank=tank,shift=second,physical_litres=D('1020')),user)
        self.check_equal(debtor.balance,D('0'))
        product.refresh_from_db()
        self.check_equal(lube_stock(product),D('3'))
        self.check_equal(statement(cash,date,date)['balance'],D('15820'))
        self.check_equal(statement(bank,date,date)['balance'],D('898'))
        self.check_equal(review_data(date)[1],[])
        transition(date,'submit',user)
        transition(date,'review',user,'Synthetic DEMO rehearsal reviewed by owner')
        self.check_equal(transition(date,'close',user).status,'CLOSED')
        try:
            Reading.objects.first().save()
        except ValidationError:
            pass
        else:
            raise CommandError('Closed-day edit was not blocked.')
        self.stdout.write(self.style.SUCCESS(f'DEMO day {date}: 160L fuel; fuel 15200; lube 100; cash 15820; bank 898; tanks 1020L each; lube 3; debtor 0; CLOSED; edit blocked.'))
