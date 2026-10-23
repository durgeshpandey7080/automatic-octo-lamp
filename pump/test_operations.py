from decimal import Decimal as D
from datetime import timedelta
from django.test import TestCase
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import *
from .services import save_shift,save_credit_sale,save_handover,save_lube_sale,staff_shift_sales
from .operations import open_duty,record_fuel_test,void_fuel_test,save_operation,reverse_operation,lube_stock
from .stock import save_stock_entry,stock_summary
from .reports import daily_report

class CompleteOperationsTests(TestCase):
 def setUp(self):
  call_command('seed_demo',verbosity=0)
  self.user=get_user_model().objects.create_user('operator',is_staff=True)
  self.person=Salesperson.objects.create(name='Operator')
  self.manager=ManagerProfile.objects.create(name='Manager')
  self.debtor=Debtor.objects.create(name='Customer')
  self.date=timezone.localdate()-timedelta(days=1)
  self.rows=[dict(salesperson=self.person,opening_litres=D('100'),closing_litres=D('110')) for _ in range(8)]
  self.shift=save_shift(self.date,1,self.rows,{'PETROL':D('100'),'DIESEL':D('90')})
 def values(self,**extra):return dict(shift=self.shift,salesperson=self.person,**extra)
 def test_integrated_testing_income_inventory_cash_bank_and_receipts(self):
  tank=Tank.objects.get(fuel='PETROL')
  save_stock_entry('opening',dict(tank=tank,date=self.date,litres=D('1000')),self.user)
  reading=self.shift.readings.get(nozzle__number=1)
  test=record_fuel_test(dict(reading=reading,litres=D('2'),disposition='RETURNED',reason='Calibration'),self.user)
  reading.refresh_from_db();self.assertEqual(reading.litres_sold,D('8'))
  self.assertEqual(stock_summary(tank,self.date)['expected'],D('962'))
  # 40 gross dispensed, 2 returned: 38 net litres leave the tank.
  income=save_operation('income',self.values(date=self.date,description='Service',amount=D('100')),self.user)
  product=LubeProduct.objects.create(name='Oil 1L',unit='BOTTLE',selling_price=D('50'))
  opening=save_operation('lube-stock',dict(product=product,date=self.date,kind='OPENING',quantity=D('5'),unit_cost=D('30')),self.user)
  purchase=save_operation('lube-stock',dict(product=product,date=self.date,kind='PURCHASE',quantity=D('3'),unit_cost=D('30'),supplier='Supplier'),self.user)
  product.refresh_from_db();self.assertEqual(lube_stock(product),D('8'))
  sale=save_lube_sale(self.values(product=product,quantity=D('2'),unit_price=D('50'),reference=''),self.user)
  self.assertEqual(lube_stock(product),D('6'))
  credit=save_credit_sale(self.debtor,self.values(amount=D('100'),reference='',notes='',vehicle_number='UP01AA1234',fuel_product='PETROL',quantity=D('1'),saved_rate=D('100')),self.user)
  self.assertTrue(credit.reference.startswith('HPN/CR/'))
  self.assertEqual(credit.vehicle_number,'UP01AA1234')
  digital=save_operation('collection',self.values(method='PAYTM',amount=D('200'),reference='REAL-UTR-1',terminal='Merchant'),self.user)
  self.assertTrue(digital.number.startswith('HPN/DC/'))
  save_operation('cash',self.values(manager=self.manager,kind='FLOAT',amount=D('500')),self.user)
  save_operation('cash',self.values(manager=self.manager,kind='RETURN',amount=D('100')),self.user)
  bank=save_operation('bank',dict(collection=digital,settlement_date=self.date,bank_name='Bank',bank_reference='BANK-1',net_received=D('198'),fee=D('2')),self.user)
  receipt=save_operation('receipt',dict(reading=reading,lube_sale=None,customer_name='Cash customer',vehicle_number='',quantity=D('8')),self.user)
  self.assertEqual(receipt.amount,D('800'))
  self.assertTrue(receipt.number.startswith('HPN/BILL/'))
  self.assertEqual(staff_shift_sales(self.shift,self.person)['amount'],D('7600'))
  handover=save_handover(self.shift,self.person,dict(submitted_to=self.manager,cash_received=D('7700'),card=D('999'),paytm_business=D('999'),phonepe_business=D('999'),notes='Collected with float and return'),self.user)
  self.assertEqual(handover.cash_adjustment,D('400'))
  self.assertEqual(handover.paytm_business,D('200'));self.assertEqual(handover.card,D('0'))
  self.assertEqual(handover.expected_cash,D('7700'));self.assertEqual(handover.status,'Balanced')
  report=daily_report(self.date)
  self.assertEqual(report['gross'],D('7600'));self.assertEqual(report['testing_litres'],D('2'))
  self.assertEqual(report['cash_returned'],D('100'))
  with self.assertRaises(ValidationError):void_fuel_test(test,self.user,'Wrong quantity')
  with self.assertRaises(ValidationError):reverse_operation('collection',digital.pk,self.user,'Wrong')
  self.assertGreater(AuditEvent.objects.count(),5)
 def test_duty_assignments_are_preserved_and_cancellation_audited(self):
  rows=[dict(salesperson=self.person,opening_litres=D('110')) for _ in range(8)]
  duty=open_duty(dict(date=self.date,number=2,petrol_price=D('100'),diesel_price=D('90')),rows,self.user)
  with self.assertRaises(ValidationError):open_duty(dict(date=self.date,number=2,petrol_price=D('100'),diesel_price=D('90')),rows,self.user)
  wrong=[dict(salesperson=self.person,opening_litres=D('111'),closing_litres=D('120')) for _ in range(8)]
  with self.assertRaises(ValidationError):save_shift(self.date,2,wrong,{'PETROL':D('100'),'DIESEL':D('90')})
  closing=[dict(salesperson=self.person,opening_litres=D('110'),closing_litres=D('120')) for _ in range(8)]
  shift2=save_shift(self.date,2,closing,{'PETROL':D('100'),'DIESEL':D('90')})
  duty.refresh_from_db();self.assertEqual(duty.closed_shift,shift2)
  with self.assertRaises(ValidationError):reverse_operation('duty',duty.pk,self.user,'Cancel closed')
  newdate=self.date+timedelta(days=1)
  duty2=open_duty(dict(date=newdate,number=1,petrol_price=D('100'),diesel_price=D('90')),[dict(salesperson=self.person,opening_litres=D('120')) for _ in range(8)],self.user)
  reverse_operation('duty',duty2.pk,self.user,'Wrong allocation')
  duty2.refresh_from_db();self.assertTrue(duty2.cancelled)
 def test_testing_reversal_and_limits(self):
  reading=self.shift.readings.get(nozzle__number=1)
  for qty,disposition in [(D('11'),'RETURNED'),(D('1'),'CONSUMED')]:
   with self.assertRaises(ValidationError):record_fuel_test(dict(reading=reading,litres=qty,disposition=disposition,reason='Test'),self.user)
  record=record_fuel_test(dict(reading=reading,litres=D('1'),disposition='RETURNED',reason='Calibration'),self.user)
  void_fuel_test(record,self.user,'Duplicate test')
  reading.refresh_from_db();self.assertEqual(reading.testing_litres,D('0'))
  with self.assertRaises(ValidationError):void_fuel_test(record,self.user,'Again')
 def test_inventory_and_receipt_overallocation(self):
  product=LubeProduct.objects.create(name='Oil',unit='BOTTLE',selling_price=D('50'))
  save_operation('lube-stock',dict(product=product,date=self.date,kind='OPENING',quantity=D('0'),unit_cost=D('0')),self.user)
  with self.assertRaises(ValidationError):save_lube_sale(self.values(product=product,quantity=D('1'),unit_price=D('50'),reference=''),self.user)
  reading=self.shift.readings.first()
  with self.assertRaises(ValidationError):save_operation('receipt',dict(reading=reading,customer_name='A',quantity=D('11')),self.user)
  self.assertEqual(SalesReceipt.objects.count(),0)
 def test_bank_amount_must_match_and_reversal_is_retained(self):
  digital=save_operation('collection',self.values(method='CARD',amount=D('100'),reference='POS-1'),self.user)
  with self.assertRaises(ValidationError):save_operation('bank',dict(collection=digital,settlement_date=self.date,bank_name='Bank',bank_reference='R1',net_received=D('95'),fee=D('1')),self.user)
  bank=save_operation('bank',dict(collection=digital,settlement_date=self.date,bank_name='Bank',bank_reference='R1',net_received=D('99'),fee=D('1')),self.user)
  reverse_operation('bank',bank.pk,self.user,'Wrong settlement reference')
  bank.refresh_from_db();self.assertTrue(bank.voided)
  reverse_operation('collection',digital.pk,self.user,'Wrong POS record')
  digital.refresh_from_db();self.assertTrue(digital.voided)
 def test_forms_numbering_auth_and_receipt_page(self):
  self.client.force_login(self.user)
  for path in ['/operations/','/duties/open/']+['/operations/'+kind+'/add/' for kind in ['testing','income','collection','lube-stock','cash','bank','receipt']]:
   self.assertEqual(self.client.get(path).status_code,200,path)
  from .forms import CreditSaleForm
  self.assertTrue(CreditSaleForm().fields['reference'].disabled)
  receipt=save_operation('receipt',dict(reading=self.shift.readings.first(),customer_name='Customer',quantity=D('1')),self.user)
  self.assertContains(self.client.get('/receipts/'+str(receipt.pk)+'/'),'not a GST tax invoice')
  self.user.is_staff=False;self.user.save()
  self.assertEqual(self.client.get('/operations/').status_code,403)

 def test_browser_forms_generate_internal_numbers_and_keep_external_ids(self):
  self.client.force_login(self.user)
  data={'date':self.date.isoformat(),'shift':self.shift.pk,'salesperson':self.person.pk,'description':'Other service','amount':'10'}
  response=self.client.post('/operations/income/add/',data)
  self.assertEqual(response.status_code,302)
  self.assertTrue(OtherIncome.objects.get().reference.startswith('HPN/OI/'))
  response=self.client.post('/operations/testing/add/',{'reading':self.shift.readings.first().pk,'litres':'1','disposition':'RETURNED','reason':'Calibration'})
  self.assertEqual(response.status_code,302)
  self.assertTrue(FuelTest.objects.get().reference.startswith('HPN/FT/'))
  response=self.client.post('/operations/receipt/add/',{'reading':self.shift.readings.first().pk,'customer_name':'Customer','quantity':'1'})
  self.assertEqual(response.status_code,302)
  response=self.client.post('/credit-sales/add/',{'debtor':self.debtor.pk,'shift':self.shift.pk,'salesperson':self.person.pk,'amount':'100','reference':'FORGED','notes':'','vehicle_number':'UP01','fuel_product':'PETROL','quantity':'1','saved_rate':'100'})
  self.assertEqual(response.status_code,302)
  self.assertNotEqual(DebtorTransaction.objects.get(kind='SALE').reference,'FORGED')

 def test_later_adjustments_respect_digital_collections_and_cash_returns(self):
  from .services import save_expense
  save_operation('collection',self.values(method='PAYTM',amount=D('7500'),reference='ALLOCATED'),self.user)
  with self.assertRaises(ValidationError):save_expense(dict(date=self.date,category='OTHER',description='Expense',payee='',voucher='TEST-EX',amount=D('200'),source='SHIFT_CASH',shift=self.shift,salesperson=self.person),self.user)
  with self.assertRaises(ValidationError):save_credit_sale(self.debtor,self.values(amount=D('200'),reference='CREDIT',notes=''),self.user)
  save_operation('cash',self.values(manager=self.manager,kind='RETURN',amount=D('50')),self.user)
  with self.assertRaises(ValidationError):save_operation('collection',self.values(method='CARD',amount=D('60'),reference='OVER-RETURN'),self.user)
  self.assertEqual(DigitalCollection.objects.count(),1)
 def test_income_reversal_cannot_create_negative_expected_cash(self):
  income=save_operation('income',self.values(date=self.date,description='Service',amount=D('100')),self.user)
  save_operation('cash',self.values(manager=self.manager,kind='RETURN',amount=D('7700')),self.user)
  with self.assertRaises(ValidationError):reverse_operation('income',income.pk,self.user,'Incorrect income')
  income.refresh_from_db();self.assertFalse(income.voided)
 def test_partial_receipts_do_not_overround_original_sale(self):
  reading=self.shift.readings.first();reading.unit_price=D('1.005');reading.save()
  receipts=[save_operation('receipt',dict(reading=reading,customer_name='Customer',quantity=D('1')),self.user) for _ in range(10)]
  self.assertEqual(sum((r.amount for r in receipts),D('0')),reading.expected_amount)
  self.assertEqual(receipts[-1].amount,D('1.00'))
