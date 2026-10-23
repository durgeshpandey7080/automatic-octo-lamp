from datetime import timedelta
from decimal import Decimal as D
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from .models import MoneyAccount, MoneyTransfer, BankAllocation, Handover, CashMovement, Expense, Shift, Salesperson, ManagerProfile, DigitalCollection, BankReconciliation, BusinessDayClose
from .money_book import statement, save_transfer, assign_bank, bank_sources


class MoneyBookTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser('book-owner', '', 'test-pass')
        self.date = timezone.localdate() - timedelta(days=1)
        self.cash = MoneyAccount.objects.create(name='Station cash', kind='CASH', opening_date=self.date, opening_balance=D('1000'), recorded_by=self.user)
        self.bank = MoneyAccount.objects.create(name='Current account', kind='BANK', opening_date=self.date, opening_balance=D('500'), recorded_by=self.user)
        self.person = Salesperson.objects.create(name='Cash staff')
        self.manager = ManagerProfile.objects.create(name='Receiving manager')
        self.shift = Shift.objects.create(date=self.date, number=1)

    def expense(self, source, amount, reference):
        return Expense.objects.create(date=self.date, source=source, amount=D(amount), voucher=reference,
            category='OTHER', description='Test expense', recorded_by=self.user,
            shift=self.shift if source == 'SHIFT_CASH' else None,
            salesperson=self.person if source == 'SHIFT_CASH' else None)

    def test_cash_counts_received_money_and_transfers_without_double_deducting_shift_expenses(self):
        Handover.objects.create(shift=self.shift, salesperson=self.person, submitted_to=self.manager,
            expected_sales=D('1000'), cash_received=D('900'), expenses=D('30'), recorded_by=self.user)
        for kind, amount in [('FLOAT','100'), ('RETURN','20')]:
            CashMovement.objects.create(shift=self.shift, salesperson=self.person, manager=self.manager,
                kind=kind, amount=D(amount), reference=kind, recorded_by=self.user)
        self.expense('SHIFT_CASH', '30', 'SHIFT-EX')
        self.expense('STATION_CASH', '50', 'OFFICE-EX')
        book = statement(self.cash, self.date, self.date)
        self.assertEqual(book['balance'], D('1770'))
        self.assertEqual(len(book['rows']), 4)
        transfer = save_transfer(dict(date=self.date, source=self.cash, destination=self.bank,
            amount=D('200'), external_reference='DEPOSIT-1', notes='Actual deposit at branch'), self.user)
        cash, bank = statement(self.cash,self.date,self.date), statement(self.bank,self.date,self.date)
        self.assertEqual(cash['balance'], D('1570'))
        self.assertEqual(bank['balance'], D('700'))
        self.assertEqual(cash['balance']+bank['balance'], D('2270'))
        with self.assertRaises(ValidationError):
            save_transfer(dict(date=self.date, source=self.cash, destination=self.bank,
                amount=D('2000'), external_reference='DEPOSIT-2', notes='Too much cash'), self.user)

    def test_bank_sources_require_assignment_and_post_only_net_settlement_once(self):
        collection = DigitalCollection.objects.create(shift=self.shift, salesperson=self.person, method='PAYTM', amount=D('100'), reference='PAYTM-REF', recorded_by=self.user)
        settlement = BankReconciliation.objects.create(collection=collection, settlement_date=self.date,
            bank_name='Current account', bank_reference='UTR-1', net_received=D('99'), fee=D('1'), recorded_by=self.user)
        expense = self.expense('BANK', '25', 'BANK-EX')
        self.assertEqual(statement(self.bank,self.date,self.date)['balance'],D('500'))
        assign_bank('SETTLEMENT', settlement.pk, self.bank, self.user)
        assign_bank('EXPENSE', expense.pk, self.bank, self.user)
        self.assertEqual(statement(self.bank,self.date,self.date)['balance'],D('574'))
        with self.assertRaises(ValidationError):
            assign_bank('SETTLEMENT', settlement.pk, self.bank, self.user)
        second_bank=MoneyAccount.objects.create(name='Second current account',kind='BANK',opening_date=self.date,opening_balance=D('0'),recorded_by=self.user)
        with self.assertRaises(ValidationError):
            assign_bank('SETTLEMENT',settlement.pk,second_bank,self.user,allow_reassign=True,correction_reason='short')
        assign_bank('SETTLEMENT',settlement.pk,second_bank,self.user,allow_reassign=True,correction_reason='Correct account from actual bank statement')
        self.assertEqual(statement(second_bank,self.date,self.date)['balance'],D('99'))
        self.assertEqual(statement(self.bank,self.date,self.date)['balance'],D('475'))
        settlement.voided = True
        settlement.save()
        self.assertEqual(statement(self.bank,self.date,self.date)['balance'],D('475'))

    def test_closed_dates_block_bulk_money_writes(self):
        BusinessDayClose.objects.create(date=self.date, status='CLOSED')
        with self.assertRaises(IntegrityError), transaction.atomic():
            MoneyTransfer.objects.bulk_create([MoneyTransfer(number='BYPASS',date=self.date,source=self.cash,destination=self.bank,amount=D('10'),external_reference='BYPASS',notes='Bypass attempt',recorded_by=self.user)])
        with self.assertRaises(ValidationError):
            self.cash.opening_balance = D('999')
            self.cash.save()

    def test_period_rendering_export_and_station_permissions(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get('/money-book/'), 'Station cash')
        response = self.client.get('/money-book/', {'start':self.date,'end':self.date,'export':'csv'})
        self.assertEqual(response.status_code,200)
        self.assertIn('text/csv', response['Content-Type'])
        self.assertIn(b'1000.00', response.content)
        other = get_user_model().objects.create_user('book-viewer')
        self.client.force_login(other)
        self.assertEqual(self.client.post('/money-book/', {'action':'account'}).status_code,403)
