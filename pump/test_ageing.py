from datetime import timedelta
from decimal import Decimal as D
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Debtor,DebtorTransaction,ManagerProfile,Salesperson,Shift
from .debtor_ageing import ageing


class DebtorAgeingTests(TestCase):
    def test_oldest_first_partial_payment_and_as_of_date(self):
        user=get_user_model().objects.create_user('age-user')
        debtor=Debtor.objects.create(name='Credit customer')
        manager=ManagerProfile.objects.create(name='Age manager')
        person=Salesperson.objects.create(name='Age salesperson')
        today=timezone.localdate()
        DebtorTransaction.objects.create(debtor=debtor,kind='OPENING',date=today-timedelta(days=100),amount=D('100'),reference='OLD',recorded_by=user)
        shift=Shift.objects.create(date=today-timedelta(days=40),number=1)
        DebtorTransaction.objects.create(debtor=debtor,kind='SALE',date=shift.date,amount=D('200'),reference='NEW',shift=shift,salesperson=person,recorded_by=user)
        DebtorTransaction.objects.create(debtor=debtor,kind='PAYMENT',date=today,amount=D('150'),reference='REPAY',payment_method='CASH',received_by=manager,recorded_by=user)
        now=ageing(today)
        self.assertEqual(now['age_totals'],[D('0'),D('150'),D('0'),D('0')])
        self.assertEqual(ageing(today-timedelta(days=1))['total_balance'],D('300'))
        self.assertEqual(debtor.balance,D('150'))
        self.client.force_login(user)
        self.assertContains(self.client.get('/debtors/ageing/'),'150.00')
        self.assertEqual(self.client.get('/debtors/ageing/',{'date':today+timedelta(days=1)}).status_code,400)
