from datetime import timedelta
from decimal import Decimal as D
from django.test import TestCase
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Salesperson,ManagerProfile,Tank
from .services import save_shift,save_handover
from .stock import save_stock_entry
from .dashboard import dashboard_graphics

class DashboardGraphicsTests(TestCase):
 def setUp(self):
  call_command('seed_demo',verbosity=0)
  self.user=get_user_model().objects.create_user('graphics-user')
  self.person=Salesperson.objects.create(name='Chart staff')
  self.date=timezone.localdate()-timedelta(days=1)
 def test_empty_charts_do_not_assume_opening_stock(self):
  graphics=dashboard_graphics(self.date)
  self.assertFalse(graphics['has_graph_data'])
  self.assertEqual(len(graphics['graph_days']),7)
  self.assertTrue(all(row['stock'] is None for row in graphics['tank_graphics']))
  self.assertEqual(graphics['collected_total'],D('0'))
  self.client.force_login(self.user)
  self.assertContains(self.client.get('/'),'Your sales story starts here')
 def test_trend_collections_and_stock_use_actual_saved_records(self):
  shift=save_shift(self.date,1,[dict(salesperson=self.person,opening_litres=D('100'),closing_litres=D('110')) for _ in range(8)],{'PETROL':D('100'),'DIESEL':D('90')})
  manager=ManagerProfile.objects.create(name='Chart manager')
  save_handover(shift,self.person,dict(submitted_to=manager,cash_received=D('5000'),card=D('100'),paytm_business=D('1000'),phonepe_business=D('500'),notes='Shortage'),self.user)
  tank=Tank.objects.get(fuel='PETROL')
  save_stock_entry('opening',dict(tank=tank,date=self.date,litres=D('1000')),self.user)
  graphics=dashboard_graphics(self.date)
  self.assertTrue(graphics['has_graph_data'])
  self.assertEqual(graphics['graph_days'][-1]['petrol'],D('40'))
  self.assertEqual(graphics['graph_days'][-1]['revenue'],D('7600'))
  self.assertEqual(graphics['graph_days'][0]['shifts'],0)
  self.assertEqual(graphics['collected_total'],D('6600'))
  self.assertAlmostEqual(sum((p['percent'] for p in graphics['collection_parts']),D('0')),D('100'))
  petrol=next(t for t in graphics['tank_graphics'] if t['tank'].pk==tank.pk)
  self.assertEqual(petrol['stock']['expected'],D('960'))
  self.assertEqual(petrol['percent'],D('4.800'))
  self.assertTrue(petrol['low'])
  self.client.force_login(self.user)
  response=self.client.get('/')
  self.assertContains(response,'View exact daily figures')
  self.assertContains(response,'No saved shift')
  self.assertContains(response,'Collection mix')
