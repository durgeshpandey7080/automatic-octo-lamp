from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import Handover,SalaryRecord,SalaryDeduction,ShortageRecovery,MoneyAccount,AuditEvent
from .advances import owner_reason,amount_check
from .salary_adjustments import remaining
from .numbering import document_number


def collectible(h):
    d=SalaryDeduction.objects.filter(handover=h).first()
    if d:
        return remaining(d)-sum((r.amount for r in h.shortage_recoveries.filter(salary=d.salary,voided=False)),Decimal('0.00'))
    return max(-h.variance,Decimal('0.00'))-sum((r.amount for r in h.shortage_recoveries.filter(voided=False)),Decimal('0.00'))


@transaction.atomic
def receive(handover_id,account_id,date,amount,reference,notes,request_id,user):
    owner_reason(user,notes);reference=reference.strip();notes=notes.strip()
    h=Handover.objects.select_for_update().select_related('shift').get(pk=handover_id)
    old=ShortageRecovery.objects.filter(request_id=request_id).first()
    if old:
        if (old.handover_id,old.account_id,old.date,old.amount,old.external_reference,old.notes)!=(handover_id,account_id,date,amount,reference,notes):raise ValidationError('Submission reference already used for another receipt.')
        return old
    account=MoneyAccount.objects.select_for_update().get(pk=account_id)
    d=SalaryDeduction.objects.filter(handover=h).first()
    salary=SalaryRecord.objects.select_for_update().get(pk=d.salary_id) if d else None
    amount_check(amount)
    if date<max(h.shift.date,account.opening_date) or date>timezone.localdate():raise ValidationError('Receipt date must follow the shortage and account opening and cannot be in the future.')
    if amount>collectible(h):raise ValidationError('Receipt exceeds the remaining shortage after waivers and earlier recoveries.')
    if account.kind=='BANK' and not reference:raise ValidationError('Bank transaction reference is required.')
    if reference and ShortageRecovery.objects.filter(account=account,external_reference=reference,voided=False).exists():raise ValidationError('This receipt transaction reference is already recorded.')
    row=ShortageRecovery(handover=h,salary=salary,account=account,date=date,amount=amount,external_reference=reference,notes=notes,request_id=request_id,number=document_number('SHREC'),recorded_by=user)
    row.full_clean();row.save()
    AuditEvent.objects.create(actor=user,model_name='ShortageRecovery',object_id=row.pk,action='shortage_received',reason=notes,after={'amount':str(amount),'salary_credit':str(amount if salary else 0),'number':row.number})
    return row


@transaction.atomic
def reverse_receipt(pk,reason,user):
    owner_reason(user,reason)
    row=ShortageRecovery.objects.select_related('handover').get(pk=pk)
    Handover.objects.select_for_update().get(pk=row.handover_id)
    row=ShortageRecovery.objects.select_for_update().get(pk=pk)
    if row.voided:return row
    if row.salary_id:
        salary=SalaryRecord.objects.select_for_update().get(pk=row.salary_id)
        if salary.outstanding_salary<row.amount:raise ValidationError('Reversal would leave salary overpaid. Correct erroneous salary payments/clearings first; actual refunds need a separate workflow.')
    elif SalaryRecord.objects.filter(salesperson=row.handover.salesperson,month__gte=row.handover.shift.date.replace(day=1)).exists():
        raise ValidationError('This receipt was included before payroll. Payroll now exists; reversal requires a separately reviewed payroll correction and is blocked here.')
    row.voided=True;row.save(update_fields=['voided'])
    from .money_book import statement
    ledger=statement(row.account,row.account.opening_date,timezone.localdate())
    if row.account.kind=='CASH' and any(r['balance']<0 for r in ledger['rows']):raise ValidationError('Reversal would leave negative recorded station cash.')
    AuditEvent.objects.create(actor=user,model_name='ShortageRecovery',object_id=row.pk,action='shortage_receipt_reversed',reason=reason,after={'voided':True})
    return row
