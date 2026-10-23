import copy
from datetime import timedelta
from decimal import Decimal as D
from unittest.mock import patch,MagicMock
from urllib.error import URLError
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.utils import timezone
from .models import *
from .owner_dashboard import station_summary,peer_summary,SALT
from .services import save_shift

@override_settings(STATION_CODE='station1',STATION_NAME='Hamara Test',OWNER_SUMMARY_PEER_URL='http://station2:8000/owner-summary/',STATION_LINKS=[{'code':'station1','name':'Hamara Test'},{'code':'station2','name':'Govind Test'}])
class OwnerDashboardTests(TestCase):
    def setUp(self):
        self.owner=get_user_model().objects.create_superuser('owner','','test-only')
        self.staff=get_user_model().objects.create_user('manager',is_staff=True)
        self.day=timezone.localdate()-timedelta(days=1)
        self.cash=MoneyAccount.objects.create(name='Cash',kind='CASH',opening_date=self.day,opening_balance=1000,recorded_by=self.owner)
        self.bank=MoneyAccount.objects.create(name='Bank',kind='BANK',opening_date=self.day,opening_balance=2000,recorded_by=self.owner)
        self.person=Salesperson.objects.create(name='Synthetic Employee')
        manager=ManagerProfile.objects.create(name='Manager')
        for fuel in ['PETROL','DIESEL']:
            tank=Tank.objects.create(name=fuel,fuel=fuel,capacity_litres=20000)
            for n in range(1 if fuel=='PETROL' else 5,5 if fuel=='PETROL' else 9):Nozzle.objects.create(number=n,tank=tank)
        rows=[dict(salesperson=self.person,opening_litres=D('100'),closing_litres=D('110')) for _ in range(8)]
        self.shift=save_shift(self.day,1,rows,{'PETROL':D('100'),'DIESEL':D('90')})
        self.h=Handover.objects.create(shift=self.shift,salesperson=self.person,submitted_to=manager,expected_sales=100,cash_received=0,recorded_by=self.owner)
        self.collection=DigitalCollection.objects.create(shift=self.shift,salesperson=self.person,method='PAYTM',amount=100,reference='synthetic-collection',recorded_by=self.owner)
    def remote(self):
        result=station_summary(self.day);result['code']='station2';result['name']='Govind Test';return result
    def auth(self,**changes):
        data=dict(username='owner',station='station1',origin='station2',date=self.day.isoformat());data.update(changes)
        return {'HTTP_X_PUMP_OWNER_SUMMARY':signing.dumps(data,salt=SALT)}
    def test_summary_dated_sales_money_and_pending(self):
        s=station_summary(self.day)
        self.assertEqual(D(s['metrics']['net_sales']),D('7600'))
        self.assertEqual(D(s['metrics']['petrol_litres']),D('40'))
        self.assertEqual(D(s['metrics']['diesel_litres']),D('40'))
        self.assertEqual(D(s['metrics']['cash']),D('1000'))
        self.assertEqual(D(s['metrics']['bank']),D('2000'))
        self.assertEqual(s['pending_digital_count'],1)
        self.assertEqual(D(s['metrics']['shortage_balance']),D('100'))
        self.assertFalse(s['complete']);self.assertTrue(s['warnings'])
        self.assertEqual(D(station_summary(self.day-timedelta(days=1))['metrics']['cash']),0)
        self.assertFalse(station_summary(self.day-timedelta(days=1))['cash_ready'])
    def test_future_settlement_not_counted_and_voided_old_match(self):
        BankReconciliation.objects.create(collection=self.collection,settlement_date=self.day,bank_name='Bank',bank_reference='old',net_received=98,fee=2,voided=True,recorded_by=self.owner)
        BankReconciliation.objects.create(collection=self.collection,settlement_date=self.day+timedelta(days=1),bank_name='Bank',bank_reference='new',net_received=98,fee=2,recorded_by=self.owner)
        self.assertEqual(station_summary(self.day)['pending_digital_count'],1)
        self.assertEqual(station_summary(self.day+timedelta(days=1))['pending_digital_count'],0)
    def test_ageing_cutoff_without_calling_debt_overdue(self):
        d=Debtor.objects.create(name='Synthetic customer')
        DebtorTransaction.objects.create(debtor=d,kind='OPENING',date=self.day-timedelta(days=45),amount=250,reference='opening',recorded_by=self.owner)
        DebtorTransaction.objects.create(debtor=d,kind='PAYMENT',date=self.day+timedelta(days=1),amount=50,reference='future',payment_method='BANK',received_by=ManagerProfile.objects.first(),recorded_by=self.owner)
        s=station_summary(self.day)
        self.assertEqual(D(s['metrics']['debt_over_30']),250)
        self.assertEqual(D(s['metrics']['debtor_balance']),250)
    def test_owner_only_and_read_only(self):
        self.assertEqual(self.client.get('/owner/').status_code,302)
        self.client.force_login(self.staff);self.assertEqual(self.client.get('/owner/').status_code,403)
        self.client.force_login(self.owner);self.assertEqual(self.client.post('/owner/',{}).status_code,405)
        self.assertEqual(self.client.get('/owner/?date=bad').status_code,400)
        self.assertEqual(self.client.get('/owner/?date='+str(timezone.localdate()+timedelta(days=1))).status_code,400)
        self.assertEqual(self.client.post('/owner-summary/',{},**self.auth()).status_code,405)
    def test_internal_summary_authentication_and_secondary_middleware(self):
        self.assertEqual(self.client.get('/owner-summary/').status_code,403)
        self.assertEqual(self.client.get('/owner-summary/',**self.auth()).status_code,200)
        self.assertEqual(self.client.get('/owner-summary/',**self.auth(username='manager')).status_code,403)
        self.assertEqual(self.client.get('/owner-summary/',**self.auth(station='station2')).status_code,403)
        self.assertEqual(self.client.get('/owner-summary/',**self.auth(origin='station1')).status_code,403)
        self.assertEqual(self.client.get('/owner-summary/',**self.auth(date='bad')).status_code,403)
        self.owner.is_active=False;self.owner.save()
        self.assertEqual(self.client.get('/owner-summary/',**self.auth()).status_code,403)
        with override_settings(STATION_CODE='station2'):
            self.assertEqual(self.client.get('/owner-summary/').status_code,403)
    def test_expired_signing_token_and_no_cache(self):
        with patch('django.core.signing.time.time',return_value=1):headers=self.auth()
        self.assertEqual(self.client.get('/owner-summary/',**headers).status_code,403)
        response=self.client.get('/owner-summary/',**self.auth())
        self.assertIn('no-store',response['Cache-Control'])
    @patch('pump.owner_dashboard.peer_summary')
    def test_combines_only_when_both_available_without_writes(self,peer):
        peer.return_value=self.remote();self.client.force_login(self.owner)
        before=(AuditEvent.objects.count(),Handover.objects.count(),MoneyAccount.objects.count())
        r=self.client.get('/owner/?date='+str(self.day))
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.context['totals']['net_sales'],15200)
        self.assertEqual(r.context['totals']['cash'],2000)
        self.assertContains(r,'Both stations, one view.')
        self.assertContains(r,'Govind Test')
        self.assertEqual(before,(AuditEvent.objects.count(),Handover.objects.count(),MoneyAccount.objects.count()))
        self.assertIn('no-store',r['Cache-Control'])
    @patch('pump.owner_dashboard.peer_summary',side_effect=URLError('offline'))
    def test_partial_outage_keeps_available_station_and_withholds_totals(self,peer):
        self.client.force_login(self.owner)
        r=self.client.get('/owner/?date='+str(self.day))
        self.assertEqual(r.status_code,503);self.assertNotIn('totals',r.context)
        self.assertContains(r,'Combined totals unavailable.',status_code=503)
        self.assertContains(r,'Hamara Test',status_code=503)
    @patch('pump.owner_dashboard.build_opener')
    def test_peer_response_schema_amounts_identity_and_timeout(self,opener):
        result=self.remote()
        response=MagicMock();response.__enter__.return_value=response
        opener.return_value.open.return_value=response
        import json
        response.read.return_value=json.dumps(result).encode()
        self.assertEqual(peer_summary(self.day,self.owner)['code'],'station2')
        self.assertEqual(opener.return_value.open.call_args.kwargs['timeout'],3)
        for key,value in [('code','station1'),('as_of','2000-01-01'),('schema',2)]:
            bad=copy.deepcopy(result);bad[key]=value;response.read.return_value=json.dumps(bad).encode()
            with self.assertRaises(ValueError):peer_summary(self.day,self.owner)
        bad=copy.deepcopy(result);bad['metrics']['cash']='NaN';response.read.return_value=json.dumps(bad).encode()
        with self.assertRaises(ValueError):peer_summary(self.day,self.owner)


    def test_shortage_waiver_return_and_business_date_cutoff(self):
        import uuid
        from .services import save_salary
        from .salary_adjustments import adjust_shortage
        from .shortages import receive
        salary=save_salary(self.person,self.day.replace(day=1),D('12000'),self.owner)
        d=salary.deductions.get()
        adjust_shortage(d.pk,D('40'),D('100'),uuid.uuid4(),'Synthetic owner shortage waiver',self.owner)
        receive(self.h.pk,self.cash.pk,self.day+timedelta(days=1),D('40'),'','Synthetic shortage receipt',uuid.uuid4(),self.owner)
        today=station_summary(self.day+timedelta(days=1))
        self.assertEqual(D(today['metrics']['shortage_balance']),0)
        self.assertEqual(D(today['metrics']['cash']),1040)
        self.assertEqual(D(station_summary(self.day)['metrics']['cash']),1000)
        self.assertEqual(D(station_summary(self.day)['metrics']['shortage_balance']),100)

    def test_unallocated_bank_receipt_not_counted_in_bank_balance(self):
        r=BankReconciliation.objects.create(collection=self.collection,settlement_date=self.day,bank_name='Bank',bank_reference='settled',net_received=98,fee=2,recorded_by=self.owner)
        s=station_summary(self.day)
        self.assertEqual(s['unallocated_bank_count'],1)
        self.assertEqual(D(s['metrics']['bank']),2000)
        BankAllocation.objects.create(kind='SETTLEMENT',source_id=r.pk,date=self.day,account=self.bank,recorded_by=self.owner)
        s=station_summary(self.day)
        self.assertEqual(s['unallocated_bank_count'],0)
        self.assertEqual(D(s['metrics']['bank']),2098)
