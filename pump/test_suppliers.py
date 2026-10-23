from decimal import Decimal as D
from datetime import timedelta
from django.test import TestCase
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Supplier,FuelPurchase,SupplierPayment,AuditEvent,Tank,Reading
from .stock import save_stock_entry,stock_summary
from .suppliers import save_purchase,save_supplier_entry,reverse_supplier_entry

class SupplierAccountsTests(TestCase):
 def setUp(self):
  call_command('seed_demo',verbosity=0)
  self.user=get_user_model().objects.create_user('purchase-user',is_staff=True)
  self.supplier=Supplier.objects.create(name='Actual supplier')
  self.date=timezone.localdate()-timedelta(days=1)
  self.tank=Tank.objects.get(fuel='PETROL')
  save_stock_entry('opening',dict(tank=self.tank,date=self.date,litres=D('1000')),self.user)
  self.delivery=save_stock_entry('delivery',dict(tank=self.tank,date=self.date,litres=D('990'),invoice='SUPPLIER-INV-1',supplier='Actual supplier'),self.user)
  self.data=dict(supplier=self.supplier,delivery=self.delivery,date=self.date,supplier_invoice='SUPPLIER-INV-1',invoiced_litres=D('1000'),unit_cost=D('80'),freight=D('500'))
 def test_invoice_partial_payment_credit_and_stock_are_separate(self):
  purchase=save_purchase(self.data,self.user)
  self.assertTrue(purchase.number.startswith('HPN/PUR/'))
  self.assertEqual(purchase.total,D('80500'))
  self.assertEqual(purchase.delivery_variance,D('-10'))
  self.assertEqual(stock_summary(self.tank,self.date)['expected'],D('1990'))
  payment=save_supplier_entry('payment',dict(purchase=purchase,date=self.date,amount=D('30000'),method='BANK',external_reference='UTR-1'),self.user)
  self.assertTrue(payment.number.startswith('HPN/SP/'))
  self.assertEqual(purchase.outstanding,D('50500'))
  credit=save_supplier_entry('credit',dict(purchase=purchase,date=self.date,amount=D('800'),supplier_credit_reference='CN-1',reason='Agreed shortage'),self.user)
  self.assertEqual(purchase.outstanding,D('49700'))
  self.assertEqual(self.supplier.outstanding,D('49700'))
  with self.assertRaises(ValidationError):reverse_supplier_entry('purchase',purchase.pk,self.user,'Wrong invoice')
  reverse_supplier_entry('payment',payment.pk,self.user,'Duplicate statement entry')
  self.assertEqual(purchase.outstanding,D('79700'))
  reverse_supplier_entry('credit',credit.pk,self.user,'Wrong credit reference')
  reverse_supplier_entry('purchase',purchase.pk,self.user,'Wrong invoice')
  self.assertEqual(self.supplier.outstanding,D('0'))
  self.assertEqual(stock_summary(self.tank,self.date)['expected'],D('1990'))
  self.assertEqual(SupplierPayment.objects.count(),1)
  self.assertGreaterEqual(AuditEvent.objects.count(),6)
 def test_overpayment_and_external_reference_validation(self):
  purchase=save_purchase(self.data,self.user)
  for amount,method,reference in [(D('80501'),'CASH',''),(D('1'),'BANK','')]:
   with self.assertRaises(ValidationError):save_supplier_entry('payment',dict(purchase=purchase,date=self.date,amount=amount,method=method,external_reference=reference),self.user)
  save_supplier_entry('payment',dict(purchase=purchase,date=self.date,amount=D('80500'),method='CASH',external_reference=''),self.user)
  with self.assertRaises(ValidationError):save_supplier_entry('credit',dict(purchase=purchase,date=self.date,amount=D('1'),supplier_credit_reference='CN-2',reason='Credit'),self.user)
 def test_duplicate_purchase_and_invalid_dates(self):
  save_purchase(self.data,self.user)
  with self.assertRaises(ValidationError):save_purchase(self.data,self.user)
  invalid=dict(self.data,date=timezone.localdate()+timedelta(days=1))
  with self.assertRaises(ValidationError):save_purchase(invalid,self.user)
  self.assertEqual(FuelPurchase.objects.count(),1)
 def test_forms_and_permissions(self):
  self.client.force_login(self.user)
  for path in ['/suppliers/','/suppliers/'+str(self.supplier.pk)+'/']+['/suppliers/entry/'+kind+'/' for kind in ['supplier','purchase','payment','credit']]:
   self.assertEqual(self.client.get(path).status_code,200,path)
  data={k:(v.pk if hasattr(v,'pk') else str(v)) for k,v in self.data.items()}
  response=self.client.post('/suppliers/entry/purchase/',data)
  self.assertEqual(response.status_code,302)
  self.assertContains(self.client.get('/suppliers/'+str(self.supplier.pk)+'/'),'80500.00')
  self.user.is_staff=False;self.user.save()
  self.assertEqual(self.client.get('/suppliers/').status_code,403)
