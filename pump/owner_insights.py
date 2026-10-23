"""Read-only dashboard calculations. Saved readings are not shift approvals."""
from datetime import datetime, timedelta
from decimal import Decimal

from django.utils import timezone
from . import models as m
from .business_clock import shift_deadline

ZERO = Decimal('0')


def sales_slots(day):
    readings = list(m.Reading.objects.filter(shift__date=day).select_related('shift', 'nozzle__tank'))
    result = []
    for number in (1, 2):
        rows = [r for r in readings if r.shift.number == number]
        result.append(dict(number=number, count=len(rows), priced=all(r.unit_price is not None for r in rows),
                           fuel_sales=str(sum((r.expected_amount or ZERO for r in rows), ZERO)),
                           petrol=str(sum((r.litres_sold for r in rows if r.nozzle.tank.fuel == 'PETROL'), ZERO)),
                           diesel=str(sum((r.litres_sold for r in rows if r.nozzle.tank.fuel == 'DIESEL'), ZERO))))
    return result


def stock_details(report, day):
    # Only complete station days contribute to consumption. Missing days aren't zero sales.
    start = day - timedelta(days=7)
    history = list(m.Reading.objects.filter(shift__date__gte=start, shift__date__lt=day)
                   .select_related('shift', 'nozzle'))
    complete_days = {start + timedelta(days=i) for i in range(7)
                     if all(sum(r.shift.date == start + timedelta(days=i) and r.shift.number == n
                                for r in history) == 8 for n in (1, 2))}
    result = []
    for row in report['stocks']:
        tank, stock = row['tank'], row['stock']
        dip = tank.dips.filter(shift__date__lte=day).select_related('shift').first()
        tank_days = {r.shift.date for r in history if r.nozzle.tank_id == tank.pk and r.shift.date in complete_days}
        sold = sum((r.closing_litres - r.opening_litres - r.returned_test_litres
                    for r in history if r.nozzle.tank_id == tank.pk and r.shift.date in tank_days), ZERO)
        average = sold / len(tank_days) if tank_days else None
        coverage = max(stock['expected'], ZERO) / average if stock and average and average > 0 and len(tank_days) >= 3 else None
        result.append(dict(name=str(tank), fuel=tank.fuel, litres=str(stock['expected']) if stock else None,
                           capacity=str(tank.capacity_litres), threshold=str(tank.low_stock_litres),
                           warning=bool(stock['warning']) if stock else True,
                           dip_litres=str(dip.physical_litres) if dip else None,
                           dip_date=dip.shift.date.isoformat() if dip else None,
                           dip_variance=str(dip.variance) if dip else None,
                           coverage=str(coverage) if coverage is not None else None,
                           history_days=len(tank_days)))
    return result


def decorate(summary, day, now=None):
    """Prepare a validated station summary for rendering, without changing records."""
    now = now or timezone.localtime()
    slots = summary['sale_slots']
    ready = [s for s in slots if s['count'] == 8 and s['priced']]
    has_sales = any(s['count'] for s in slots)
    baseline = summary['baseline_slots']
    compare_ready = bool(ready) and len(ready) == sum(s['count'] > 0 for s in slots)
    matching = [b for b in baseline if any(s['number'] == b['number'] for s in ready)]
    compare_ready &= len(matching) == len(ready) and all(b['count'] == 8 and b['priced'] for b in matching)
    previous = sum((Decimal(b['fuel_sales']) for b in matching), ZERO)
    current = sum((Decimal(s['fuel_sales']) for s in ready), ZERO)
    percent = (current - previous) / previous * 100 if compare_ready and previous > 0 else None
    summary['view'] = dict(has_sales=has_sales, priced=all(s['priced'] for s in slots),
                           recorded=len(ready), compare_available=percent is not None,
                           comparison_current=current, comparison_previous=previous,
                           percent=percent, percent_abs=abs(percent) if percent is not None else None,
                           trend='up' if percent is not None and percent >= 0 else 'down',
                           matched_slots=[s['number'] for s in ready],
                           checked=datetime.fromisoformat(summary['checked_at']))
    for slot in slots:
        due = shift_deadline(day, slot['number'])
        slot['overdue'] = slot['count'] < 8 and now > due
        slot['ready'] = slot['count'] == 8 and slot['priced']
    for tank in summary['stocks']:
        amount = Decimal(tank['litres']) if tank['litres'] is not None else None
        capacity, threshold = Decimal(tank['capacity']), Decimal(tank['threshold'])
        tank['fill'] = min(100, max(0, amount / capacity * 100)) if amount is not None else 0
        tank['low'] = amount is not None and amount <= threshold
        tank['threshold_invalid'] = threshold > capacity
        tank['urgent'] = tank['coverage'] is not None and Decimal(tank['coverage']) < 1
        tank['dip_stale'] = tank['dip_date'] != day.isoformat()
    return summary
