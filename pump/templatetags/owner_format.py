from decimal import Decimal, InvalidOperation
from django import template

register = template.Library()


@register.filter
def inr(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite(): return '—'
        whole, fraction = f'{abs(amount):.2f}'.split('.')
        tail, head = whole[-3:], whole[:-3]
        groups = []
        while head:
            groups.insert(0, head[-2:])
            head = head[:-2]
        return ('−' if amount < 0 else '') + ','.join(groups + [tail]) + '.' + fraction
    except (InvalidOperation, ValueError, TypeError):
        return '—'
