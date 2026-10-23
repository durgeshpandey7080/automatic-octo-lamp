from decimal import Decimal
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.utils import timezone
from .models import SalaryAdvance,SalaryRecord,SalaryPayment,MoneyAccount,AuditEvent
from .numbering import document_number


@transaction.atomic
def record_payment(salary_id,account_id,date,amount,reference,notes,request_id,user):
    if not user.is_superuser:raise PermissionDenied
    reference,notes=reference.strip(),notes.strip()
    salary=SalaryRecord.objects.select_for_update().get(pk=salary_id)
    existing=SalaryPayment.objects.filter(request_id=request_id).first()
    if existing:
        if (existing.salary_id,existing.account_id,existing.date,existing.amount,existing.external_reference,existing.notes)!=(salary.pk,account_id,date,amount,reference,notes):
            raise ValidationError('This submission reference was used for a different payment.')
        return existing
    account=MoneyAccount.objects.select_for_update().get(pk=account_id)
    if date>timezone.localdate() or date<max(account.opening_date,salary.month):
        raise ValidationError('Payment date must be on/after the salary month and account opening, and cannot be in the future.')
    if not amount.is_finite() or amount<=0 or amount!=amount.quantize(Decimal('0.01')) or amount>salary.outstanding_salary:
        raise ValidationError('Payment must be positive, at most two decimals, and cannot exceed outstanding salary.')
    if len(notes)<10:raise ValidationError('Add a payment explanation of at least 10 characters.')
    if account.kind=='BANK' and not reference:raise ValidationError('Enter the bank transaction reference.')
    if reference and (SalaryPayment.objects.filter(account=account,external_reference=reference,voided=False).exists() or SalaryAdvance.objects.filter(account=account,external_reference=reference,voided=False).exists()):
        raise ValidationError('That account transaction reference is already recorded.')
    entry=SalaryPayment(salary=salary,account=account,date=date,amount=amount,external_reference=reference,notes=notes,request_id=request_id,number=document_number('SALPAY'),recorded_by=user)
    entry.full_clean();entry.save()
    from .money_book import statement
    if account.kind=='CASH':
        ledger=statement(account,account.opening_date,timezone.localdate())
        if ledger['balance']<0 or any(row['balance']<0 for row in ledger['rows']):
            raise ValidationError('Payment would leave negative recorded station cash. Check balances and dates.')
    AuditEvent.objects.create(actor=user,model_name='SalaryPayment',object_id=entry.pk,action='salary_payment',reason=notes,after={'amount':str(amount),'number':entry.number,'account':account.pk})
    return entry


@transaction.atomic
def reverse_payment(pk,reason,user):
    if not user.is_superuser:raise PermissionDenied
    reason=reason.strip()
    if len(reason)<10:raise ValidationError('Explain the correction in at least 10 characters.')
    payment=SalaryPayment.objects.select_related('salary').get(pk=pk)
    SalaryRecord.objects.select_for_update().get(pk=payment.salary_id)
    payment=SalaryPayment.objects.select_for_update().get(pk=pk)
    if payment.voided:return payment
    payment.voided=True;payment.save(update_fields=['voided'])
    AuditEvent.objects.create(actor=user,model_name='SalaryPayment',object_id=payment.pk,action='salary_payment_reversed',reason=reason,before={'voided':False},after={'voided':True})
    return payment
