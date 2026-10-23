from datetime import datetime,time,timedelta
from decimal import Decimal as D
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Tank,TankQualityObservation,FuelDelivery
from .quality_views import QualityForm


class QualityTests(TestCase):
    def setUp(self):
        self.owner=get_user_model().objects.create_superuser('quality-owner','','test-pass')
        self.tank=Tank.objects.create(name='Quality tank',fuel='PETROL',capacity_litres=D('20000'))
        self.date=timezone.localdate()-timedelta(days=1)
        self.values=dict(tank=self.tank,date=self.date,kind='MORNING',observed_at=timezone.make_aware(datetime.combine(self.date,time(9))),observed_density=D('740'),temperature_c=D('25'),density_15c=D('742'),correction_source='Verified instrument',water_mm=D('0'),recorded_by=self.owner)

    def test_density_correction_reference_and_delivery_tank_date_validation(self):
        observation=TankQualityObservation(**self.values)
        observation.full_clean()
        observation.correction_source=''
        with self.assertRaises(ValidationError): observation.full_clean()
        observation.correction_source='Verified instrument'
        observation.kind='DELIVERY'
        with self.assertRaises(ValidationError): observation.full_clean()
        delivery=FuelDelivery.objects.create(tank=self.tank,date=self.date,litres=D('100'),invoice='QUALITY-INV',number='QUALITY-DELIVERY',recorded_by=self.owner)
        observation.delivery=delivery
        observation.full_clean()
        observation.save()
        self.assertEqual(observation.observed_density,D('740'))
        self.assertEqual(observation.density_15c,D('742'))

    def test_unique_morning_history_and_readonly_access(self):
        row=TankQualityObservation(**self.values)
        row.full_clean();row.save()
        duplicate=TankQualityObservation(**self.values)
        with self.assertRaises(ValidationError):duplicate.full_clean()
        viewer=get_user_model().objects.create_user('quality-reader')
        self.client.force_login(viewer)
        self.assertContains(self.client.get('/quality/'),'740.00')
        self.assertEqual(self.client.post('/quality/',{}).status_code,403)
