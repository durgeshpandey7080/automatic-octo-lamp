from decimal import Decimal
from .models import Debtor


def ageing(date):
    """Read-only oldest-first estimate; never changes repayment allocations."""
    accounts = []
    totals = [Decimal('0.00') for _ in range(4)]
    for debtor in Debtor.objects.prefetch_related('transactions').order_by('name'):
        unpaid = []
        for entry in sorted((e for e in debtor.transactions.all() if e.date <= date), key=lambda e: (e.date, e.created_at, e.pk)):
            if entry.kind in {'OPENING', 'SALE'}:
                unpaid.append({'entry': entry, 'remaining': entry.amount})
            else:
                amount = entry.amount
                for item in unpaid:
                    applied = min(amount, item['remaining'])
                    item['remaining'] -= applied
                    amount -= applied
                    if amount <= 0:
                        break
        unpaid = [i for i in unpaid if i['remaining'] > 0]
        buckets = [Decimal('0.00') for _ in range(4)]
        for item in unpaid:
            days = (date - item['entry'].date).days
            index = 0 if days <= 30 else 1 if days <= 60 else 2 if days <= 90 else 3
            buckets[index] += item['remaining']
        balance = sum(buckets, Decimal('0.00'))
        if balance:
            accounts.append({'debtor': debtor, 'buckets': buckets, 'balance': balance,
                'oldest': min(i['entry'].date for i in unpaid), 'items': unpaid})
            totals = [a+b for a,b in zip(totals,buckets)]
    return {'accounts': accounts, 'age_totals': totals, 'total_balance': sum(totals, Decimal('0.00'))}
