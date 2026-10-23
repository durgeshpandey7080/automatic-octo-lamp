from decimal import Decimal
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.utils import timezone
from .models import SalaryAdvance,AdvanceRecovery,Salesperson,SalaryRecord,MoneyAccount,SalaryPayment,AuditEvent
from .numbering import document_number


def amount_check(amount):
    if not amount.is_finite() or amount<=0 or amount!=amount.quantize(Decimal('0.01')):
        raise ValidationError('Enter a positive amount with at most two decimals.')


def owner_reason(user,reason):
    if not user.is_superuser:raise PermissionDenied
    if len(reason.strip())<10:raise ValidationError('Explain the entry in at least 10 characters.')


@transaction.atomic
def record_advance(person_id,account_id,date,amount,reference,notes,request_id,user):
    owner_reason(user,notes);reference=reference.strip();notes=notes.strip()
    person=Salesperson.objects.select_for_update().get(pk=person_id)
    old=SalaryAdvance.objects.filter(request_id=request_id).first()
    if old:
        if (old.salesperson_id,old.account_id,old.date,old.amount,old.external_reference,old.notes)!=(person_id,account_id,date,amount,reference,notes):raise ValidationError('Submission reference already used.')
        return old
    if not person.active:raise ValidationError('Choose an active employee.')
    account=MoneyAccount.objects.select_for_update().get(pk=account_id)
    amount_check(amount)
    if date>timezone.localdate() or date<account.opening_date:raise ValidationError('Date cannot precede account opening or be in the future.')
    if account.kind=='BANK' and not reference:raise ValidationError('Bank transaction reference is required.')
    if reference and (SalaryAdvance.objects.filter(account=account,external_reference=reference,voided=False).exists() or SalaryPayment.objects.filter(account=account,external_reference=reference,voided=False).exists()):raise ValidationError('This account transaction reference is already recorded.')
    entry=SalaryAdvance(salesperson=person,account=account,date=date,amount=amount,external_reference=reference,notes=notes,request_id=request_id,number=document_number('ADV'),recorded_by=user)
    entry.full_clean();entry.save()
    from .money_book import statement
    ledger=statement(account,account.opening_date,timezone.localdate())
    if account.kind=='CASH' and (ledger['balance']<0 or any(r['balance']<0 for r in ledger['rows'])):raise ValidationError('Advance would leave negative recorded station cash.')
    AuditEvent.objects.create(actor=user,model_name='SalaryAdvance',object_id=entry.pk,action='advance_recorded',reason=notes,after={'amount':str(amount),'account':account.pk})
    return entry


@transaction.atomic
def apply_advance(advance_id,salary_id,date,amount,reason,request_id,user):
    owner_reason(user,reason);reason=reason.strip()
    salary=SalaryRecord.objects.select_for_update().get(pk=salary_id)
    advance=SalaryAdvance.objects.select_for_update().get(pk=advance_id)
    old=AdvanceRecovery.objects.filter(request_id=request_id).first()
    if old:
        if (old.advance_id,old.salary_id,old.date,old.amount,old.reason)!=(advance_id,salary_id,date,amount,reason):raise ValidationError('Submission reference already used.')
        return old
    amount_check(amount)
    if advance.voided or salary.salesperson_id!=advance.salesperson_id:raise ValidationError('Select an active advance and a salary for the same employee.')
    if date>timezone.localdate() or date<max(advance.date,salary.month):raise ValidationError('Clearing date must be on/after advance and salary month and not in the future.')
    if amount>advance.remaining_amount or amount>salary.outstanding_salary:raise ValidationError('Clearing cannot exceed remaining advance or outstanding salary.')
    row=AdvanceRecovery(advance=advance,salary=salary,date=date,amount=amount,reason=reason,request_id=request_id,recorded_by=user)
    row.full_clean();row.save()
    AuditEvent.objects.create(actor=user,model_name='AdvanceRecovery',object_id=row.pk,action='advance_applied',reason=reason,after={'advance':advance.number,'salary':salary.pk,'amount':str(amount),'money_moved':'0'})
    return row


@transaction.atomic
def reverse_advance(kind,pk,reason,user):
    owner_reason(user,reason)
    if kind=='advance':
        row=SalaryAdvance.objects.select_for_update().get(pk=pk)
        if row.recoveries.filter(voided=False).exists():raise ValidationError('Reverse linked salary clearings before correcting this advance.')
    elif kind=='recovery':
        row=AdvanceRecovery.objects.get(pk=pk)
        SalaryRecord.objects.select_for_update().get(pk=row.salary_id)
        SalaryAdvance.objects.select_for_update().get(pk=row.advance_id)
        row=AdvanceRecovery.objects.select_for_update().get(pk=pk)
    else:raise ValidationError('Unknown record type.')
    if row.voided:return row
    row.voided=True;row.save(update_fields=['voided'])
    AuditEvent.objects.create(actor=user,model_name=type(row).__name__,object_id=row.pk,action='advance_reversed',reason=reason.strip(),before={'voided':False},after={'voided':True})
    return row
