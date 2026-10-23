import hashlib
import json
from decimal import Decimal
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone
from . import models as m
from .access import can_manage
from .reports import daily_report

# Used for fingerprints and database-level date locks. Relations keep every source date.
SOURCES = {
    'ShortageRecovery': ['date'], 'SalaryAdvance': ['date'], 'AdvanceRecovery': ['date'],
    'SalaryPayment': ['date'],
    'BulkSaleAllocation': ['reading__shift__date'],
    'ShiftDiscount': ['shift__date'],
    'TankQualityObservation': ['date'],
    'MoneyAccount': ['opening_date'], 'MoneyTransfer': ['date'], 'BankAllocation': ['date'],
    'Shift': ['date'], 'DailyFuelPrice': ['date'], 'Reading': ['shift__date'],
    'Handover': ['shift__date'], 'DebtorTransaction': ['date', 'shift__date'],
    'Expense': ['date', 'shift__date'], 'LubeSale': ['shift__date'],
    'TankOpening': ['date'], 'FuelDelivery': ['date'], 'TankDip': ['shift__date'],
    'Duty': ['date'], 'DutyAssignment': ['duty__date'], 'FuelTest': ['reading__shift__date'],
    'OtherIncome': ['date', 'shift__date'], 'DigitalCollection': ['shift__date'],
    'LubeMovement': ['date'], 'CashMovement': ['shift__date'],
    'BankReconciliation': ['settlement_date'],
    'SalesReceipt': ['reading__shift__date', 'lube_sale__shift__date'],
    'FuelPurchase': ['date', 'delivery__date'], 'SupplierPayment': ['date'], 'SupplierCredit': ['date'],
}


def review_data(date):
    from django.db.models import Q
    report = daily_report(date)
    rows = {}
    for name, paths in SOURCES.items():
        query = Q()
        for path in paths:
            # Earlier inventory entries affect today's running balances too.
            query |= Q(**{path + '__lte': date})
        rows[name] = list(getattr(m, name).objects.filter(query).order_by('pk').values())
    for name in ['Tank', 'Nozzle', 'LubeProduct', 'Debtor', 'Salesperson', 'ManagerProfile']:
        rows[name] = list(getattr(m, name).objects.order_by('pk').values())
    digest = hashlib.sha256(json.dumps(rows, cls=DjangoJSONEncoder, sort_keys=True).encode()).hexdigest()
    issues = []
    if not report['complete']:
        issues.append('Sales or handovers are incomplete (two shifts and eight readings per shift are required).')
    if m.Duty.objects.filter(date=date, closed_shift=None, cancelled=False).exists():
        issues.append('An open duty has not been completed.')
    for item in report['stocks']:
        if item['stock'] is None:
            issues.append(f"Opening stock unavailable: {item['tank']}.")
        elif item['stock']['warning']:
            issues.append(f"Book stock outside tank capacity: {item['tank']}.")
        if not item['dip']:
            issues.append(f"Closing physical dip missing: {item['tank']}.")
        elif item['dip'].variance != 0:
            issues.append(f"Physical stock variance: {item['tank']}.")
        morning = m.TankQualityObservation.objects.filter(tank=item['tank'], date=date, kind='MORNING', voided=False).first()
        if not morning:
            issues.append(f"Morning density/water observation missing: {item['tank']}.")
        elif morning.water_mm > 0 or morning.density_15c is None:
            issues.append(f"Morning water/density result needs review: {item['tank']}.")
    for delivery in m.FuelDelivery.objects.filter(date=date):
        observation = m.TankQualityObservation.objects.filter(delivery=delivery, kind='DELIVERY', voided=False).first()
        if not observation or observation.water_mm > 0 or observation.density_15c is None:
            issues.append(f"After-delivery quality observation missing or needs review: {delivery.number}.")
    if report['totals']['shortage'] or report['totals']['excess']:
        issues.append('Cash handovers contain a shortage or excess requiring review.')
    snapshot = json.loads(json.dumps({'date': date, 'gross': report['gross'],
        'fuel': report['fuel'], 'lube_total': report['lube_total'], 'totals': report['totals'],
        'expense_total': report['expense_total'], 'repayment_total': report['repayment_total'],
        'issues': issues}, cls=DjangoJSONEncoder))
    return report, issues, snapshot, digest


@transaction.atomic
def transition(date, action, user, reason=''):
    if date > timezone.localdate():
        raise ValidationError('Future days cannot be closed.')
    day, _ = m.BusinessDayClose.objects.get_or_create(date=date)
    day = m.BusinessDayClose.objects.select_for_update().get(pk=day.pk)
    before = {'status': day.status, 'fingerprint': day.fingerprint}
    report, issues, snapshot, digest = review_data(date)
    reason = reason.strip()
    if action == 'submit':
        if day.status == 'CLOSED':
            raise ValidationError('Reopen this closed day first.')
        if not m.Shift.objects.filter(date=date).exists():
            raise ValidationError('Save at least one shift before submitting this day.')
        day.status = 'SUBMITTED'
        day.submitted_by = user
        day.submitted_at = timezone.now()
        day.reviewed_by = day.closed_by = None
        day.reviewed_at = day.closed_at = None
        day.snapshot, day.fingerprint = snapshot, digest
    elif action == 'review':
        if not can_manage(user):
            raise PermissionDenied
        if day.status != 'SUBMITTED':
            raise ValidationError('Submit the day before manager review.')
        if day.submitted_by_id == user.pk and not (user.is_superuser and reason):
            raise ValidationError('A different manager must review, or the owner must explain a self-review override.')
        if day.fingerprint != digest:
            raise ValidationError('Records changed since submission. Submit the day again.')
        day.status = 'REVIEWED'
        day.reviewed_by, day.reviewed_at = user, timezone.now()
    elif action == 'close':
        if not can_manage(user):
            raise PermissionDenied
        if day.status != 'REVIEWED':
            raise ValidationError('Manager review is required before closing.')
        if day.fingerprint != digest:
            raise ValidationError('Records changed since review. Submit and review again.')
        if issues and not (user.is_superuser and len(reason) >= 10):
            raise ValidationError('Resolve listed exceptions, or the owner must give an explanation of at least 10 characters.')
        if m.BusinessDayClose.objects.filter(date__gt=date, status='CLOSED').exists():
            raise ValidationError('A later day is closed. Reopen later closed days first.')
        day.status = 'CLOSED'
        day.closed_by, day.closed_at = user, timezone.now()
        day.exception_reason = reason if issues else ''
        day.snapshot = snapshot
    elif action == 'reopen':
        if not user.is_superuser:
            raise PermissionDenied
        if day.status != 'CLOSED' or len(reason) < 10:
            raise ValidationError('A closed day and a reopening reason of at least 10 characters are required.')
        if m.BusinessDayClose.objects.filter(date__gt=date, status='CLOSED').exists():
            raise ValidationError('Reopen the most recent closed day first.')
        day.status = 'DRAFT'
    else:
        raise ValidationError('Unknown closing action.')
    day.save()
    m.AuditEvent.objects.create(actor=user, model_name='pump.BusinessDayClose', object_id=day.pk,
        action=action, reason=reason or 'Daily closing workflow', before=before,
        after={'status': day.status, 'fingerprint': day.fingerprint, 'exceptions': issues})
    return day
