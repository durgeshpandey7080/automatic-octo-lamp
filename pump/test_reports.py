from decimal import Decimal as D
from datetime import timedelta
from django.test import TestCase
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Salesperson, ManagerProfile
from .services import save_shift, save_handover
from .reports import daily_report

class DailyReportTests(TestCase):
    def setUp(self):
        call_command('seed_demo',verbosity=0)
        self.user=get_user_model().objects.create_user('report-user')
        self.person=Salesperson.objects.create(name='Report Staff')
        self.manager=ManagerProfile.objects.create(name='Report Manager')
        self.date=timezone.localdate()-timedelta(days=1)
    def test_partial_day_does_not_assume_cash_received(self):
        shift=save_shift(self.date,1,[dict(salesperson=self.person,opening_litres=D('100'),closing_litres=D('110')) for _ in range(8)],{'PETROL':D('100'),'DIESEL':D('90')})
        report=daily_report(self.date)
        self.assertFalse(report['complete'])
        self.assertEqual(report['gross'],D('7600'))
        self.assertEqual(report['fuel']['PETROL']['litres'],D('40'))
        self.assertEqual(report['fuel']['DIESEL']['amount'],D('3600'))
        self.assertEqual(len(report['pending']),1)
        self.assertEqual(report['totals']['cash_received'],D('0'))
        save_handover(shift,self.person,dict(submitted_to=self.manager,cash_received=D('7490'),card=D('100'),paytm_business=D('0'),phonepe_business=D('0'),notes='Short by ten'),self.user)
        report=daily_report(self.date)
        self.assertEqual(report['totals']['shortage'],D('10'))
        self.assertEqual(report['totals']['excess'],D('0'))
        self.assertFalse(report['complete'])
        shift2=save_shift(self.date,2,[dict(salesperson=self.person,opening_litres=D('110'),closing_litres=D('110')) for _ in range(8)],{'PETROL':D('100'),'DIESEL':D('90')})
        save_handover(shift2,self.person,dict(submitted_to=self.manager,cash_received=D('0'),card=D('0'),paytm_business=D('0'),phonepe_business=D('0'),notes=''),self.user)
        self.assertTrue(daily_report(self.date)['complete'])
        self.assertEqual(daily_report(self.date-timedelta(days=1))['gross'],D('0'))
    def test_date_validation_auth_and_rendering(self):
        self.assertEqual(self.client.get('/reports/daily/').status_code,302)
        self.client.force_login(self.user)
        self.assertContains(self.client.get('/reports/daily/'),'Incomplete day')
        for value in ['bad-date',(timezone.localdate()+timedelta(days=1)).isoformat()]:
            self.assertEqual(self.client.get('/reports/daily/',{'date':value}).status_code,400)


    def test_shift_workspace_links_and_locks(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get('/workspace/'), 'Start with the nozzle readings')
        shift=save_shift(self.date,1,[dict(salesperson=self.person,opening_litres=D('100'),closing_litres=D('110')) for _ in range(8)],{'PETROL':D('100'),'DIESEL':D('90')})
        response=self.client.get('/workspace/',{'shift':shift.pk})
        self.assertContains(response,'Add customer credit')
        self.assertContains(response,'7600.00')
        self.assertContains(response,'salesperson='+str(self.person.pk))
        save_handover(shift,self.person,dict(submitted_to=self.manager,cash_received=D('7600'),card=D('0'),paytm_business=D('0'),phonepe_business=D('0'),notes=''),self.user)
        response=self.client.get('/workspace/',{'shift':shift.pk})
        self.assertContains(response,'View handover')
        self.assertNotContains(response,'Add customer credit')
