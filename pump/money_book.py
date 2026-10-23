from decimal import Decimal
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.utils import timezone
from .models import *
from .access import can_manage
from .numbering import document_number

ZERO = Decimal('0.00')


def bank_sources(end):
    """Only actual net bank movements; a sale is never a second receipt."""
    result = []
    for record in BankReconciliation.objects.filter(settlement_date__lte=end, voided=False).select_related('collection'):
        if record.collection.voided:
            continue
        result.append(dict(kind='SETTLEMENT', source_id=record.pk, date=record.settlement_date,
            amount=record.net_received, label='Settlement ' + record.bank_reference))
    for record in Expense.objects.filter(date__lte=end, source='BANK'):
        result.append(dict(kind='EXPENSE', source_id=record.pk, date=record.date, amount=-record.amount, label='Expense ' + record.voucher))
    for record in DebtorTransaction.objects.filter(date__lte=end, kind='PAYMENT', payment_method='BANK'):
        result.append(dict(kind='DEBTOR', source_id=record.pk, date=record.date, amount=record.amount, label='Debtor repayment ' + record.reference))
    for record in SupplierPayment.objects.filter(date__lte=end, method='BANK', voided=False):
        result.append(dict(kind='SUPPLIER', source_id=record.pk, date=record.date, amount=-record.amount, label='Supplier payment ' + record.number))
    allocation = {(a.kind, a.source_id): a for a in BankAllocation.objects.select_related('account')}
    for row in result:
        row['allocation'] = allocation.get((row['kind'], row['source_id']))
    return sorted(result, key=lambda r: (r['date'], r['kind'], r['source_id']))


def cash_sources(end):
    rows = []
    def add(date, amount, label, ref):
        rows.append(dict(date=date, amount=amount, label=label, reference=ref))
    for h in Handover.objects.filter(shift__date__lte=end).select_related('shift', 'salesperson'):
        add(h.shift.date, h.cash_received, 'Salesperson handover · ' + str(h.salesperson), 'HANDOVER-' + str(h.pk))
    for r in CashMovement.objects.filter(shift__date__lte=end, voided=False).select_related('shift'):
        add(r.shift.date, r.amount if r.kind == 'RETURN' else -r.amount, r.get_kind_display(), r.reference)
    # Shift-cash expenses already reduced the cash actually handed to the manager.
    for r in Expense.objects.filter(date__lte=end, source='STATION_CASH'):
        add(r.date, -r.amount, 'Station expense · ' + r.category, r.voucher)
    for r in DebtorTransaction.objects.filter(date__lte=end, kind='PAYMENT', payment_method='CASH'):
        add(r.date, r.amount, 'Debtor cash repayment', r.reference)
    for r in SupplierPayment.objects.filter(date__lte=end, method='CASH', voided=False):
        add(r.date, -r.amount, 'Supplier cash payment', r.number)
    for p in SalaryPayment.objects.filter(date__lte=end,account__kind='CASH',voided=False).select_related('salary__salesperson'):
        add(p.date,-p.amount,'Salary payment '+str(p.salary.salesperson),p.number)
    for a in SalaryAdvance.objects.filter(date__lte=end,account__kind='CASH',voided=False).select_related('salesperson'):
        add(a.date,-a.amount,'Staff advance '+str(a.salesperson),a.number)
    for r in ShortageRecovery.objects.filter(date__lte=end,account__kind='CASH',voided=False):
        add(r.date,r.amount,'Shortage recovery',r.number)
    return rows


def statement(account, start, end):
    rows = cash_sources(end) if account.kind == 'CASH' else [
        dict(date=r['date'], amount=r['amount'], label=r['label'], reference=r['kind'] + '-' + str(r['source_id']))
        for r in bank_sources(end) if r['allocation'] and r['allocation'].account_id == account.pk]
    if account.kind=='BANK':
        for r in ShortageRecovery.objects.filter(account=account,date__lte=end,voided=False):
            rows.append(dict(date=r.date,amount=r.amount,label='Shortage recovery',reference=r.number))
        for a in SalaryAdvance.objects.filter(account=account,date__lte=end,voided=False).select_related('salesperson'):
            rows.append(dict(date=a.date,amount=-a.amount,label='Staff advance '+str(a.salesperson),reference=a.number))
        for p in SalaryPayment.objects.filter(account=account,date__lte=end,voided=False).select_related('salary__salesperson'):
            rows.append(dict(date=p.date,amount=-p.amount,label='Salary payment '+str(p.salary.salesperson),reference=p.number))
    for transfer in MoneyTransfer.objects.filter(date__lte=end, voided=False):
        if transfer.source_id == account.pk:
            rows.append(dict(date=transfer.date, amount=-transfer.amount, label='Transfer to ' + str(transfer.destination), reference=transfer.number))
        if transfer.destination_id == account.pk:
            rows.append(dict(date=transfer.date, amount=transfer.amount, label='Transfer from ' + str(transfer.source), reference=transfer.number))
    rows = sorted((r for r in rows if r['date'] >= account.opening_date), key=lambda r: (r['date'], r['reference']))
    opening = account.opening_balance + sum((r['amount'] for r in rows if r['date'] < start), ZERO)
    balance = opening
    selected = []
    for row in rows:
        if row['date'] >= start:
            balance += row['amount']
            selected.append(dict(row, balance=balance, incoming=max(row['amount'], ZERO), outgoing=max(-row['amount'], ZERO)))
    return {'account': account, 'opening': opening, 'balance': balance, 'rows': selected,
            'incoming': sum((r['incoming'] for r in selected), ZERO), 'outgoing': sum((r['outgoing'] for r in selected), ZERO)}


@transaction.atomic
def save_transfer(data, user):
    if not can_manage(user):
        raise PermissionDenied
    date = data['date']
    if date > timezone.localdate():
        raise ValidationError('Future transfers are not allowed.')
    if data['source'].pk == data['destination'].pk:
        raise ValidationError('Select different source and destination accounts.')
    if date < max(data['source'].opening_date, data['destination'].opening_date):
        raise ValidationError('Transfer cannot precede either account opening date.')
    # Validate once more at the service boundary, not only in the form.
    record = MoneyTransfer(**data, number=document_number('MT'), recorded_by=user)
    record.full_clean()
    if record.source.kind == 'CASH' and statement(record.source, date, date)['balance'] < record.amount:
        raise ValidationError('Insufficient recorded station cash for this transfer. Check the opening balance and entries.')
    record.save()
    AuditEvent.objects.create(actor=user, model_name='pump.MoneyTransfer', object_id=record.pk, action='create',
        reason=record.notes, after={'number': record.number, 'amount': str(record.amount)})
    return record


@transaction.atomic
def assign_bank(kind, source_id, account, user, allow_reassign=False, correction_reason=''):
    if not can_manage(user):
        raise PermissionDenied
    if account.kind != 'BANK':
        raise ValidationError('Choose a bank account.')
    source = next((r for r in bank_sources(timezone.localdate()) if r['kind'] == kind and r['source_id'] == source_id), None)
    if not source:
        raise ValidationError('This source is unavailable or already assigned.')
    if source['date'] < account.opening_date:
        raise ValidationError('The bank movement precedes this account opening date.')
    before = {}
    if source['allocation']:
        if not allow_reassign:
            raise ValidationError('This source is already assigned. Only the owner may make a reasoned correction.')
        if not user.is_superuser:
            raise PermissionDenied
        if len(correction_reason.strip()) < 10:
            raise ValidationError('Explain the bank-account correction in at least 10 characters.')
        record = BankAllocation.objects.select_for_update().get(pk=source['allocation'].pk)
        before = {'account': record.account.name}
        record.account = account
    else:
        record = BankAllocation(kind=kind, source_id=source_id, date=source['date'], account=account, recorded_by=user)
    record.full_clean()
    record.save()
    AuditEvent.objects.create(actor=user, model_name='pump.BankAllocation', object_id=record.pk, action='assign',
        reason=correction_reason.strip() if before else 'Bank account assigned to existing source', before=before,
        after={'kind': kind, 'source_id': source_id, 'account': account.name})
    return record
