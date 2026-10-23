import csv
import hashlib
import io
from datetime import date
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.utils import timezone
from .models import PaymentImportBatch, PaymentEvidence, DigitalCollection, AuditEvent
from .access import can_manage


def preview_csv(raw):
    if len(raw) > 2 * 1024 * 1024:
        raise ValidationError('CSV limit is 2 MB.')
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ValidationError('Save the CSV as UTF-8.')
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or not {'reference', 'date', 'amount', 'status'} <= set(reader.fieldnames):
        raise ValidationError('Use the template columns: reference,date,amount,status,description. Dates must be YYYY-MM-DD.')
    if len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValidationError('Duplicate CSV headings are not allowed.')
    rows, seen = [], set()
    try:
        for line, row in enumerate(reader, 2):
            if len(rows) >= 10000:
                raise ValidationError('Maximum 10,000 rows per import.')
            reference = row['reference'].strip()
            if not reference or len(reference) > 100 or reference in seen:
                raise ValueError('Missing, too long or duplicate transaction reference')
            seen.add(reference)
            if row['status'].strip().upper() != 'SUCCESS':
                raise ValueError('Only SUCCESS rows are supported; filter pending, failed, refund and reversal rows separately')
            observed = date.fromisoformat(row['date'].strip())
            if observed > timezone.localdate():
                raise ValueError('Future transaction dates are not allowed')
            amount = Decimal(row['amount'].strip())
            if not amount.is_finite() or amount <= 0 or amount > Decimal('9999999999.99') or amount.quantize(Decimal('.01')) != amount:
                raise ValueError('Amount must be positive with at most two decimal places')
            rows.append({'reference': reference, 'date': observed.isoformat(), 'amount': str(amount),
                         'description': (row.get('description') or '').strip()[:200]})
    except (ValueError, InvalidOperation, KeyError, AttributeError, TypeError, csv.Error) as exc:
        raise ValidationError(f'CSV row {line}: {exc}')
    if not rows:
        raise ValidationError('The file contains no transaction rows.')
    return {'checksum': hashlib.sha256(raw).hexdigest(), 'rows': rows}


@transaction.atomic
def commit_import(preview, provider, merchant, user):
    if not can_manage(user):
        raise PermissionDenied
    if provider not in {'PAYTM', 'PHONEPE'} or not merchant.strip() or len(merchant) > 100:
        raise ValidationError('Select a supported provider and actual merchant identifier.')
    merchant = merchant.strip()
    batch, created = PaymentImportBatch.objects.get_or_create(provider=provider, merchant=merchant,
        checksum=preview['checksum'], defaults={'imported_by': user})
    if not created:
        return batch, False
    for row in preview['rows']:
        record, new = PaymentEvidence.objects.get_or_create(provider=provider, merchant=merchant, reference=row['reference'],
            defaults={'batch': batch, 'date': row['date'], 'amount': row['amount'], 'description': row['description']})
        if not new and (record.date.isoformat() != row['date'] or record.amount != Decimal(row['amount'])):
            raise ValidationError('A previously imported reference has a different date or amount. Nothing from this file was committed; investigate the provider report.')
        batch.new_rows += int(new)
        batch.duplicate_rows += int(not new)
    batch.save(update_fields=['new_rows', 'duplicate_rows'])
    AuditEvent.objects.create(actor=user, model_name='pump.PaymentImportBatch', object_id=batch.pk, action='import',
        reason='User-confirmed successful-payment evidence CSV; no financial postings created',
        after={'provider': provider, 'merchant': merchant, 'new_rows': batch.new_rows, 'duplicates': batch.duplicate_rows})
    return batch, True


@transaction.atomic
def match_evidence(pk, collection_id, user):
    if not can_manage(user):
        raise PermissionDenied
    evidence = PaymentEvidence.objects.select_for_update().get(pk=pk)
    collection = DigitalCollection.objects.select_for_update().select_related('shift').get(pk=collection_id, voided=False)
    if evidence.collection_id:
        raise ValidationError('Evidence is already matched.')
    if (evidence.provider != collection.method or evidence.reference != collection.reference or
            evidence.amount != collection.amount or evidence.date != collection.shift.date or
            (collection.terminal and evidence.merchant != collection.terminal)):
        raise ValidationError('Provider, reference, amount, business date and recorded merchant must agree. Resolve mismatches rather than forcing a match.')
    evidence.collection, evidence.matched_by, evidence.matched_at = collection, user, timezone.now()
    evidence.save(update_fields=['collection', 'matched_by', 'matched_at'])
    AuditEvent.objects.create(actor=user, model_name='pump.PaymentEvidence', object_id=evidence.pk,
        action='match', reason='Exact payment evidence matched; bank settlement still requires separate reconciliation',
        after={'collection': collection.pk})
    return evidence
