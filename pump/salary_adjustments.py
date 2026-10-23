from decimal import Decimal
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from .models import SalaryRecord, SalaryDeduction, SalaryShortageAdjustment, AuditEvent


def remaining(deduction):
    last=deduction.adjustments.order_by('-pk').first()
    return last.revised_amount if last else deduction.amount


@transaction.atomic
def adjust_shortage(deduction_id, revised, expected, request_id, reason, user):
    if not user.is_superuser:
        raise PermissionDenied
    reason=reason.strip()
    if len(reason)<10:
        raise ValidationError('Explain the adjustment in at least 10 characters.')
    row=SalaryDeduction.objects.select_for_update().get(pk=deduction_id)
    existing=SalaryShortageAdjustment.objects.filter(request_id=request_id).first()
    if existing:
        if (existing.deduction_id,existing.revised_amount,existing.reason)!=(row.pk,revised,reason):
            raise ValidationError('This submission reference was already used for another adjustment.')
        return existing
    if not revised.is_finite() or revised<0 or revised>row.amount or revised!=revised.quantize(Decimal('0.01')):
        raise ValidationError('Revised deduction must be between zero and the original shortage, with at most two decimals.')
    salary=SalaryRecord.objects.select_for_update().get(pk=row.salary_id)
    current=remaining(row)
    recovered=sum((r.amount for r in row.handover.shortage_recoveries.filter(salary=salary,voided=False)), Decimal('0.00'))
    if revised<recovered:raise ValidationError('Revised deduction cannot be below money already recovered. Correct an erroneous receipt first.')
    if salary.adjusted_net_salary+current-revised<salary.paid_amount+salary.advance_applied:
        raise ValidationError('This adjustment would reduce salary due below recorded payments. Correct an erroneous payment first; actual refunds need a separate workflow.')
    if current!=expected:
        raise ValidationError('This deduction changed. Refresh the page before trying again.')
    if current==revised:
        raise ValidationError('The revised deduction is unchanged.')
    entry=SalaryShortageAdjustment(deduction=row,request_id=request_id,previous_amount=current,revised_amount=revised,reason=reason,recorded_by=user)
    entry.full_clean();entry.save()
    AuditEvent.objects.create(action='salary_shortage_adjustment',model_name='SalaryShortageAdjustment',object_id=entry.pk,reason=reason,actor=user,before={'deduction':str(current)},after={'deduction':str(revised),'salary_credit':str(entry.salary_credit)})
    return entry
