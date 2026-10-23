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
        for key,value in [('code','station1'),('as_of','2000-01-01'),('schema',3)]:
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

    def baseline_readings(self, day, number=1, multiplier=D('0.5')):
        shift=Shift.objects.create(date=day,number=number)
        for reading in self.shift.readings.all():
            Reading.objects.create(shift=shift,nozzle=reading.nozzle,salesperson=self.person,
                opening_litres=100,closing_litres=110,unit_price=reading.unit_price*multiplier)
        return shift

    def test_comparison_matches_only_complete_priced_shift_slots(self):
        from .owner_insights import decorate
        baseline=self.baseline_readings(self.day-timedelta(days=7))
        summary=decorate(station_summary(self.day),self.day)
        self.assertEqual(summary['view']['percent'],100)
        self.assertEqual(summary['view']['matched_slots'],[1])
        baseline.readings.first().delete()
        self.assertFalse(decorate(station_summary(self.day),self.day)['view']['compare_available'])

    def test_zero_baseline_and_empty_day_do_not_imply_a_change(self):
        from .owner_insights import decorate
        baseline=self.baseline_readings(self.day-timedelta(days=7))
        baseline.readings.update(closing_litres=100)
        self.assertFalse(decorate(station_summary(self.day),self.day)['view']['compare_available'])
        empty=decorate(station_summary(self.day-timedelta(days=1)),self.day-timedelta(days=1))
        self.assertFalse(empty['view']['has_sales'])

    @patch('pump.owner_dashboard.peer_summary')
    def test_empty_day_displays_missing_data_and_missing_cash_opening(self,peer):
        empty_day=self.day-timedelta(days=1)
        peer.return_value=station_summary(empty_day)
        self.client.force_login(self.owner)
        response=self.client.get('/owner/?date='+str(empty_day))
        self.assertContains(response,'Your day is taking shape.')
        self.assertFalse(response.context['has_sales'])
        self.assertFalse(response.context['cash_ready'])
        self.assertContains(response,'Missing entries are not zero sales.')

    def test_grace_period_is_for_readings_not_approval(self):
        from datetime import datetime
        from .owner_insights import decorate
        at=lambda hour,minute:timezone.make_aware(datetime.combine(self.day,datetime.min.time()).replace(hour=hour,minute=minute))
        before=decorate(station_summary(self.day),self.day,now=at(22,30))
        self.assertFalse(before['sale_slots'][1]['overdue'])
        after=decorate(station_summary(self.day),self.day,now=at(22,31))
        self.assertTrue(after['sale_slots'][1]['overdue'])
        self.assertTrue(after['sale_slots'][0]['ready'])

    def test_stock_threshold_dip_freshness_and_sparse_history(self):
        from .owner_insights import decorate
        tank=Tank.objects.get(fuel='PETROL')
        TankOpening.objects.create(tank=tank,date=self.day-timedelta(days=10),litres=4500,recorded_by=self.owner)
        closing=Shift.objects.create(date=self.day,number=2)
        TankDip.objects.create(tank=tank,shift=closing,physical_litres=4450,expected_litres=4460,recorded_by=self.owner)
        row=next(r for r in decorate(station_summary(self.day),self.day)['stocks'] if r['fuel']=='PETROL')
        self.assertTrue(row['low']);self.assertEqual(row['threshold'],'5000.000')
        self.assertFalse(row['dip_stale']);self.assertEqual(D(row['dip_variance']),-10)
        self.assertIsNone(row['coverage'])
        tank.low_stock_litres=4000;tank.save()
        row=next(r for r in decorate(station_summary(self.day+timedelta(days=1)),self.day+timedelta(days=1))['stocks'] if r['fuel']=='PETROL')
        self.assertFalse(row['low']);self.assertTrue(row['dip_stale'])

    def test_peer_rejects_nonfinite_stock_and_incomplete_slot_details(self):
        from .owner_dashboard import validate_details
        result=self.remote();result['stocks'][0]['capacity']='NaN'
        with self.assertRaises(ValueError):validate_details(result)
        result=self.remote();result['sale_slots'][0]['count']=9
        with self.assertRaises(ValueError):validate_details(result)

    def test_indian_currency_grouping_and_nonfinite_values(self):
        from .templatetags.owner_format import inr
        self.assertEqual(inr('1234567.80'),'12,34,567.80')
        self.assertEqual(inr('-1234'),'−1,234.00')
        self.assertEqual(inr('NaN'),'—')

    def test_stock_coverage_excludes_missing_days_and_warns_under_one_day(self):
        from .owner_insights import decorate
        tank=Tank.objects.get(fuel='PETROL')
        TankOpening.objects.create(tank=tank,date=self.day-timedelta(days=7),litres=300,recorded_by=self.owner)
        for offset in (1,3,5):
            for number in (1,2):self.baseline_readings(self.day-timedelta(days=offset),number=number)
        row=next(r for r in decorate(station_summary(self.day),self.day)['stocks'] if r['fuel']=='PETROL')
        # 3 complete days consume 80 L/day; current shift consumes 40 L: 20 L remain.
        self.assertEqual(row['history_days'],3)
        self.assertEqual(D(row['coverage']),D('0.25'))
        self.assertTrue(row['urgent'])
