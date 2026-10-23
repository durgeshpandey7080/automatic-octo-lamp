import uuid
from datetime import timedelta
from decimal import Decimal as D
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction, IntegrityError
from django.utils import timezone
from .models import Salesperson,ManagerProfile,SalaryShortageAdjustment,ShiftDiscount,AuditEvent,BusinessDayClose
from .services import save_shift,save_handover,save_salary,staff_shift_sales
from .salary_adjustments import adjust_shortage
from .discounts import save_discount,reverse_discount
from .reports import daily_report

class AdjustmentTests(TestCase):
    def setUp(self):
        call_command('seed_demo',verbosity=0)
        self.owner=get_user_model().objects.create_superuser('adjust-owner','','test-only')
        self.staff=get_user_model().objects.create_user('adjust-staff',is_staff=True)
        self.person=Salesperson.objects.create(name='DEMO employee')
        self.manager=ManagerProfile.objects.create(name='DEMO manager')
        self.date=timezone.localdate()-timedelta(days=1)
        self.shift=save_shift(self.date,1,[dict(salesperson=self.person,opening_litres=D('100'),closing_litres=D('110')) for _ in range(8)],{'PETROL':D('100'),'DIESEL':D('90')})

    def salary(self):
        h=save_handover(self.shift,self.person,dict(submitted_to=self.manager,cash_received=D('7500'),card=D('0'),paytm_business=D('0'),phonepe_business=D('0'),notes='DEMO shortage 100'),self.owner)
        salary=save_salary(self.person,self.date.replace(day=1),D('12000'),self.owner)
        return h,salary,salary.deductions.get()

    def test_salary_credit_restore_retry_and_stale_form(self):
        h,s,d=self.salary(); token=uuid.uuid4()
        a=adjust_shortage(d.pk,D('40'),D('100'),token,'Owner approves reduced deduction',self.owner)
        self.assertEqual(s.adjusted_net_salary,D('11960'))
        self.assertEqual(adjust_shortage(d.pk,D('40'),D('100'),token,a.reason,self.owner).pk,a.pk)
        self.assertEqual(SalaryShortageAdjustment.objects.count(),1)
        with self.assertRaises(ValidationError):
            adjust_shortage(d.pk,D('0'),D('100'),uuid.uuid4(),'Stale owner adjustment request',self.owner)
        adjust_shortage(d.pk,D('100'),D('40'),uuid.uuid4(),'Owner reverses earlier adjustment',self.owner)
        self.assertEqual(s.adjusted_net_salary,D('11900'))
        adjust_shortage(d.pk,D('0'),D('100'),uuid.uuid4(),'Owner waives remaining deduction',self.owner)
        self.assertEqual(s.adjusted_net_salary,D('12000'))
        h.refresh_from_db();s.refresh_from_db()
        self.assertEqual(h.variance,D('-100'));self.assertEqual(s.shortage_deduction,D('100'))
        self.assertEqual(s.deductions.count(),1)
        self.assertEqual(AuditEvent.objects.filter(action='salary_shortage_adjustment').count(),3)

    def test_salary_bounds_permissions_and_append_only(self):
        h,s,d=self.salary()
        for value in [D('-1'),D('101'),D('0.001')]:
            with self.assertRaises(ValidationError):
                adjust_shortage(d.pk,value,D('100'),uuid.uuid4(),'Invalid amount attempt',self.owner)
        with self.assertRaises(PermissionDenied):
            adjust_shortage(d.pk,D('0'),D('100'),uuid.uuid4(),'Unauthorized adjustment attempt',self.staff)
        a=adjust_shortage(d.pk,D('0'),D('100'),uuid.uuid4(),'Approved full deduction waiver',self.owner)
        with self.assertRaises(IntegrityError),transaction.atomic():
            SalaryShortageAdjustment.objects.filter(pk=a.pk).update(reason='tamper')
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(f'/salaries/deductions/{d.pk}/adjust/',{}).status_code,403)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get('/salaries/'),'12000.00')
        self.assertEqual(self.client.get(f'/salaries/deductions/{d.pk}/adjust/').status_code,200)

    def test_discount_net_handover_report_and_idempotence(self):
        token=uuid.uuid4()
        d=save_discount(self.shift,self.person,D('100'),'DEMO approved customer discount',token,self.owner)
        self.assertEqual(save_discount(self.shift,self.person,D('100'),d.reason,token,self.owner).pk,d.pk)
        self.assertEqual(staff_shift_sales(self.shift,self.person)['amount'],D('7500'))
        self.assertEqual(daily_report(self.date)['gross'],D('7600'))
        self.assertEqual(daily_report(self.date)['net_sales'],D('7500'))
        h=save_handover(self.shift,self.person,dict(submitted_to=self.manager,cash_received=D('7500'),card=D('0'),paytm_business=D('0'),phonepe_business=D('0'),notes='DEMO approved discount'),self.owner)
        self.assertEqual(h.variance,D('0'))
        with self.assertRaises(ValidationError):reverse_discount(d.pk,'Too late to reverse discount',self.owner)
        with self.assertRaises(ValidationError):save_discount(self.shift,self.person,D('1'),'Too late to add another',uuid.uuid4(),self.owner)
        self.assertEqual(ShiftDiscount.objects.count(),1)

    def test_discount_bounds_reverse_permissions_and_closed_date(self):
        with self.assertRaises(PermissionDenied):save_discount(self.shift,self.person,D('10'),'Staff must not approve discount',uuid.uuid4(),self.staff)
        for value in [D('-1'),D('0'),D('7601')]:
            with self.assertRaises(ValidationError):save_discount(self.shift,self.person,value,'Invalid discount attempt',uuid.uuid4(),self.owner)
        d=save_discount(self.shift,self.person,D('100'),'Approved sample discount',uuid.uuid4(),self.owner)
        reverse_discount(d.pk,'Owner cancelled this discount',self.owner)
        self.assertEqual(staff_shift_sales(self.shift,self.person)['amount'],D('7600'))
        BusinessDayClose.objects.create(date=self.date,status='CLOSED')
        with self.assertRaises(ValidationError):save_discount(self.shift,self.person,D('10'),'Closed period discount attempt',uuid.uuid4(),self.owner)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get('/workspace/').status_code,200)
        self.assertEqual(self.client.get(f'/discounts/{self.shift.pk}/{self.person.pk}/add/').status_code,200)

    def test_bulk_allocation_never_adds_another_sale(self):
        from .bulk_views import save_bulk
        from .models import BulkSaleAllocation
        reading=self.shift.readings.first()
        before=daily_report(self.date)['gross']
        token=uuid.uuid4()
        entry=save_bulk(reading,D('8'),'DEMO bulk customer','DEMO TRUCK','Nozzle sale already included',token,self.owner)
        self.assertEqual(save_bulk(reading,D('8'),'DEMO bulk customer','DEMO TRUCK',entry.reason,token,self.owner).pk,entry.pk)
        self.assertEqual(BulkSaleAllocation.objects.count(),1)
        self.assertEqual(daily_report(self.date)['gross'],before)
        self.assertEqual(staff_shift_sales(self.shift,self.person)['amount'],D('7600'))
        with self.assertRaises(ValidationError):
            save_bulk(reading,D('3'),'Other buyer','','Would exceed sold litres',uuid.uuid4(),self.owner)
        from .operations import record_fuel_test
        with self.assertRaises(ValidationError):
            record_fuel_test(dict(reading=reading,litres=D('3'),disposition='RETURNED',reason='Must preserve bulk allocations'),self.owner)
        BusinessDayClose.objects.create(date=self.date,status='CLOSED')
        with self.assertRaises(ValidationError):
            save_bulk(reading,D('1'),'Other buyer','','Closed day must be locked',uuid.uuid4(),self.owner)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get('/bulk-sales/').status_code,200)
        response=self.client.get('/daily-workbench/?date='+str(self.date))
        self.assertContains(response,'Money allocation check')
        self.assertContains(response,'Ready for handover')
