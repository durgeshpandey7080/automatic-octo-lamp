from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, F
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Tank, TankOpening, FuelDelivery, TankDip, Reading, Shift

def stock_summary(tank, date=None):
    date = date or timezone.localdate()
    opening = TankOpening.objects.filter(tank=tank).first()
    if not opening or date < opening.date:
        return None
    delivered = FuelDelivery.objects.filter(tank=tank,date__gte=opening.date,date__lte=date).aggregate(total=Sum('litres'))['total'] or Decimal('0.000')
    readings = Reading.objects.filter(nozzle__tank=tank,shift__date__gte=opening.date,shift__date__lte=date)
    sold = readings.aggregate(total=Sum(F('closing_litres')-F('opening_litres')-F('returned_test_litres')))['total'] or Decimal('0.000')
    latest = Shift.objects.filter(date__gte=opening.date,date__lte=date).order_by('-date','-number').first()
    expected = opening.litres + delivered - sold
    return {'opening':opening, 'delivered':delivered,'sold':sold,'expected':expected,
        'latest_shift':latest,'warning':expected<0 or expected>tank.capacity_litres}

@transaction.atomic
def save_stock_entry(kind, data, user):
    from .numbering import document_number
    data=dict(data)
    if kind=='delivery':data['number']=document_number('FD')
    tank = Tank.objects.select_for_update().get(pk=data['tank'].pk)
    if kind == 'opening':
        if TankOpening.objects.filter(tank=tank).exists():
            raise ValidationError('Opening stock is already set for this tank.')
        record = TankOpening(**data,recorded_by=user)
        date = record.date
        if record.litres > tank.capacity_litres:
            raise ValidationError('Opening stock exceeds tank capacity.')
    else:
        opening = TankOpening.objects.filter(tank=tank).first()
        if not opening:
            raise ValidationError('Set this tank opening stock first.')
        if kind == 'delivery':
            record = FuelDelivery(**data,recorded_by=user)
            date = record.date
            if record.litres > tank.capacity_litres:
                raise ValidationError('A single delivery cannot exceed tank capacity.')
            if TankDip.objects.filter(tank=tank,shift__date__gte=date).exists():
                raise ValidationError('That date has a saved dip. Earlier deliveries cannot be added after closing stock is saved.')
        elif kind == 'dip':
            shift = data['shift']
            date = shift.date
            if shift.number != 2 or shift.readings.count() != 8:
                raise ValidationError('Record both shifts and all eight readings before the end-of-day dip.')
            if TankDip.objects.filter(tank=tank,shift__date__gt=date).exists():
                raise ValidationError('Record dips in business-date order.')
            if data['physical_litres'] > tank.capacity_litres:
                raise ValidationError('Dip stock exceeds tank capacity.')
            summary = stock_summary(tank,date)
            if summary is None:
                raise ValidationError('Dip date must be on or after opening date.')
            record = TankDip(**data,expected_litres=summary['expected'],recorded_by=user)
        else:
            raise ValidationError('Unknown stock entry type.')
        if date < opening.date:
            raise ValidationError('Date cannot be before the tank opening date.')
    if date > timezone.localdate():
        raise ValidationError('Future stock entries are not allowed.')
    record.full_clean(); record.save()
    return record
