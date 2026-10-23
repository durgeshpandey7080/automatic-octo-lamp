from decimal import Decimal
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from .models import Shift, ShiftDiscount, AuditEvent
from .services import unlocked_staff_shift, check_adjustment_limit


@transaction.atomic
def save_discount(shift,person,amount,reason,request_id,user):
    if not user.is_superuser:
        raise PermissionDenied
    reason=reason.strip()
    if len(reason)<10:
        raise ValidationError('Explain the discount in at least 10 characters.')
    existing=ShiftDiscount.objects.filter(request_id=request_id).first()
    if existing:
        if (existing.shift_id,existing.salesperson_id,existing.amount,existing.reason)!=(shift.pk,person.pk,amount,reason):
            raise ValidationError('This submission reference has already been used.')
        return existing
    shift,summary=unlocked_staff_shift(shift,person)
    if not amount.is_finite() or amount<=0 or amount!=amount.quantize(Decimal('0.01')) or amount>summary['fuel_amount']+summary['lube_amount']-summary['discount_amount']:
        raise ValidationError('Discount must be positive and cannot exceed remaining fuel and lube sales.')
    check_adjustment_limit(shift,person,Decimal('0'),summary['amount']-amount)
    entry=ShiftDiscount(shift=shift,salesperson=person,amount=amount,reason=reason,request_id=request_id,recorded_by=user)
    entry.full_clean();entry.save()
    AuditEvent.objects.create(action='discount_approved',model_name='ShiftDiscount',object_id=entry.pk,reason=reason,actor=user,after={'amount':str(amount),'shift':shift.pk,'salesperson':person.pk})
    return entry


@transaction.atomic
def reverse_discount(pk,reason,user):
    if not user.is_superuser:
        raise PermissionDenied
    reason=reason.strip()
    if len(reason)<10:
        raise ValidationError('Explain the reversal in at least 10 characters.')
    entry=ShiftDiscount.objects.select_for_update().get(pk=pk)
    unlocked_staff_shift(entry.shift,entry.salesperson)
    if entry.voided:
        return entry
    entry.voided=True;entry.save(update_fields=['voided'])
    AuditEvent.objects.create(action='discount_reversed',model_name='ShiftDiscount',object_id=entry.pk,reason=reason,actor=user,before={'voided':False},after={'voided':True})
    return entry
