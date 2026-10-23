from decimal import Decimal as D
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Tank, Salesperson, TankDip, FuelDelivery
from .stock import save_stock_entry, stock_summary
from .services import save_shift

class TankStockTests(TestCase):
    def setUp(self):
        call_command('seed_demo',verbosity=0)
        self.user=get_user_model().objects.create_user('stock-user')
        self.person=Salesperson.objects.create(name='Stock Staff')
        self.tank=Tank.objects.get(fuel='PETROL')
        self.date=timezone.localdate()-timedelta(days=1)
    def opening(self):
        return save_stock_entry('opening',dict(tank=self.tank,date=self.date,litres=D('1000')),self.user)
    def shift(self,number,start):
        return save_shift(self.date,number,[dict(salesperson=self.person,opening_litres=D(start),closing_litres=D(start)+10) for _ in range(8)],{'PETROL':D('100'),'DIESEL':D('90')})
    def test_sales_deliveries_and_saved_dip_variance(self):
        self.opening()
        self.shift(1,'100'); close=self.shift(2,'110')
        save_stock_entry('delivery',dict(tank=self.tank,date=self.date,litres=D('500'),invoice='INV-1',supplier='HPCL',notes=''),self.user)
        summary=stock_summary(self.tank,self.date)
        self.assertEqual(summary['sold'],D('80'))
        self.assertEqual(summary['expected'],D('1420'))
        self.assertIsNone(stock_summary(Tank.objects.get(fuel='DIESEL'),self.date))
        dip=save_stock_entry('dip',dict(tank=self.tank,shift=close,physical_litres=D('1415'),notes='Measured'),self.user)
        self.assertEqual(dip.variance,D('-5'))
        self.assertEqual(stock_summary(self.tank,self.date)['expected'],D('1420'))
        with self.assertRaises(ValidationError):
            save_stock_entry('delivery',dict(tank=self.tank,date=self.date,litres=D('10'),invoice='LATE',supplier='HPCL'),self.user)
        with self.assertRaises(ValidationError):
            save_stock_entry('dip',dict(tank=self.tank,shift=close,physical_litres=D('1415')),self.user)
        self.assertEqual(TankDip.objects.count(),1)
    def test_opening_and_delivery_validation(self):
        with self.assertRaises(ValidationError):
            save_stock_entry('delivery',dict(tank=self.tank,date=self.date,litres=D('20'),invoice='NO-OPEN',supplier='HPCL'),self.user)
        self.opening()
        for date,litres in [(self.date-timedelta(days=1),D('10')),(timezone.localdate()+timedelta(days=1),D('10')),(self.date,D('0')),(self.date,D('25000'))]:
            with self.assertRaises(ValidationError):
                save_stock_entry('delivery',dict(tank=self.tank,date=date,litres=litres,invoice='INVALID',supplier='HPCL'),self.user)
        with self.assertRaises(ValidationError):
            self.opening()
        self.assertEqual(FuelDelivery.objects.count(),0)
    def test_dip_requires_end_of_day_and_capacity(self):
        self.opening(); first=self.shift(1,'100')
        with self.assertRaises(ValidationError):
            save_stock_entry('dip',dict(tank=self.tank,shift=first,physical_litres=D('950')),self.user)
        close=self.shift(2,'110')
        with self.assertRaises(ValidationError):
            save_stock_entry('dip',dict(tank=self.tank,shift=close,physical_litres=D('21000')),self.user)
    def test_stock_views_and_auth(self):
        self.assertEqual(self.client.get('/stock/').status_code,302)
        self.client.force_login(self.user)
        self.assertContains(self.client.get('/stock/'),'No balance has been assumed')
        for kind in ['opening','delivery','dip']:
            self.assertEqual(self.client.get('/stock/'+kind+'/add/').status_code,200)
        self.assertEqual(self.client.get('/stock/unknown/add/').status_code,404)
