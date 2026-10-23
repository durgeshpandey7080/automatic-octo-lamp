from datetime import timedelta
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import Nozzle, Shift, Reading, DailyFuelPrice, Handover, ManagerProfile, Debtor, DebtorTransaction, Expense, LubeProduct, LubeSale

def latest_shift():
    return Shift.objects.order_by('-date', '-number').first()

def next_slot(previous):
    if previous.number == 1:
        return previous.date, 2
    return previous.date + timedelta(days=1), 1

@transaction.atomic
def save_shift(date, number, rows, prices=None):
    # SQLite is for one local operator. Unique constraints also reject duplicate slots.
    nozzles = list(Nozzle.objects.select_for_update().order_by('number'))
    if [n.number for n in nozzles] != list(range(1, 9)) or len(rows) != 8:
        raise ValidationError('Configure exactly nozzles 1 through 8 and submit all eight rows.')
    previous = latest_shift()
    if previous and (date, number) != next_slot(previous):
        raise ValidationError('Enter the next consecutive shift after ' + str(previous) + '.')
    if not previous and number != 1:
        raise ValidationError('Your first recorded shift must be Shift 1.')
    from .models import Duty
    duty=Duty.objects.filter(date=date,number=number,closed_shift=None,cancelled=False).first()
    if Duty.objects.filter(closed_shift=None,cancelled=False).exclude(pk=duty.pk if duty else None).exists():
        raise ValidationError('Close the open duty before entering another shift.')
    if duty:
        assignments=list(duty.assignments.order_by('nozzle__number'))
        if len(assignments)!=8:raise ValidationError('Duty assignments are incomplete.')
        for a,row in zip(assignments,rows):
            if row['salesperson'].pk!=a.salesperson_id or row['opening_litres']!=a.opening_litres:
                raise ValidationError('Closing must use the saved duty salesperson and opening meters.')
        for fuel in ['PETROL','DIESEL']:
            if Decimal(str((prices or {}).get(fuel,0)))!=getattr(duty,fuel.lower()+'_price'):
                raise ValidationError('Use the prices saved when duty started.')
    previous_rows = {r.nozzle_id: r for r in previous.readings.all()} if previous else {}
    if previous and len(previous_rows) != 8:
        raise ValidationError('The previous shift is incomplete. Ask the administrator to investigate.')
    shift = Shift(date=date, number=number)
    shift.full_clean()
    rates = {}
    for fuel in {nozzle.tank.fuel for nozzle in nozzles}:
        try:
            value = Decimal(str((prices or {}).get(fuel, '')))
        except (InvalidOperation, ValueError):
            raise ValidationError(f'Enter the {fuel.lower()} price for this business date.')
        price = DailyFuelPrice(date=date, fuel=fuel, price_per_litre=value)
        # Validate field precision/range without rejecting the existing date/fuel key.
        price.clean_fields()
        existing = DailyFuelPrice.objects.select_for_update().filter(date=date, fuel=fuel).first()
        if existing and existing.price_per_litre != value:
            raise ValidationError(f'{fuel.title()} price is already saved at Rs {existing.price_per_litre}/L for {date}. Both shifts must use the same daily price.')
        if not existing:
            price.save()
        rates[fuel] = value
    shift.save()
    for nozzle, values in zip(nozzles, rows):
        old = previous_rows.get(nozzle.pk)
        if old and values['opening_litres'] != old.closing_litres:
            raise ValidationError(f'Nozzle {nozzle.number}: opening litres must equal the previous closing.')
        person = values.get('salesperson')
        if not person or not person.active:
            raise ValidationError(f'Nozzle {nozzle.number}: select an active salesperson.')
        reading = Reading(shift=shift, nozzle=nozzle, unit_price=rates[nozzle.tank.fuel],
            salesperson=person, opening_litres=values['opening_litres'], closing_litres=values['closing_litres'])
        reading.full_clean()
        reading.save()
    if duty:
        duty.closed_shift=shift; duty.save()
    return shift


def staff_shift_sales(shift, salesperson):
    readings = list(shift.readings.select_related('nozzle__tank'))
    if len(readings) != 8 or any(r.unit_price is None or r.salesperson_id is None for r in readings):
        raise ValidationError('This shift needs eight priced readings with salesperson assignments before handover.')
    assigned = [r for r in readings if r.salesperson_id == salesperson.pk]
    lube_sales = list(shift.lube_sales.filter(salesperson=salesperson).select_related('product'))
    if not assigned and not lube_sales:
        raise ValidationError('This salesperson has no readings assigned in this shift.')
    fuel_litres = {fuel: sum((r.litres_sold for r in assigned if r.nozzle.tank.fuel == fuel), Decimal('0'))
        for fuel in ['PETROL', 'DIESEL']}
    fuel_amount = sum((r.expected_amount for r in assigned), Decimal('0.00'))
    lube_amount = sum((entry.amount for entry in lube_sales), Decimal('0.00'))
    from .models import OtherIncome, ShiftDiscount
    income_amount=sum((e.amount for e in OtherIncome.objects.filter(shift=shift,salesperson=salesperson,voided=False)),Decimal('0.00'))
    discount_amount=sum((d.amount for d in ShiftDiscount.objects.filter(shift=shift,salesperson=salesperson,voided=False)),Decimal('0.00'))
    return {
        'discount_amount':discount_amount, 'gross_amount':fuel_amount+lube_amount+income_amount,
        'income_amount':income_amount,
        'readings': assigned,
        'litres': sum((r.litres_sold for r in assigned), Decimal('0')),
        'petrol_litres': fuel_litres['PETROL'], 'diesel_litres': fuel_litres['DIESEL'],
        'fuel_amount': fuel_amount, 'lube_amount': lube_amount, 'lube_sales': lube_sales,
        'amount': fuel_amount + lube_amount + income_amount - discount_amount,
    }


@transaction.atomic
def save_handover(shift, salesperson, values, recorded_by):
    # Compute from saved readings; never trust a posted expected total.
    shift = Shift.objects.select_for_update().get(pk=shift.pk)
    summary = staff_shift_sales(shift, salesperson)
    if Handover.objects.filter(shift=shift, salesperson=salesperson).exists():
        raise ValidationError('Handover is already recorded for this salesperson and shift.')
    submitted_to = values.get('submitted_to')
    if not submitted_to or not ManagerProfile.objects.filter(pk=submitted_to.pk, active=True).exists():
        raise ValidationError('Select an active manager as the cash recipient.')
    from .operations import cash_adjustment, digital_totals
    values=dict(values)
    tracked=digital_totals(shift,salesperson)
    if tracked is not None:values.update(tracked)
    from .numbering import document_number
    handover = Handover(number=document_number('HO'),cash_adjustment=cash_adjustment(shift,salesperson), shift=shift, salesperson=salesperson, expected_sales=summary['amount'],
        submitted_to=submitted_to, recorded_by=recorded_by,
        **handover_adjustments(shift, salesperson)['totals'],
        **{key: values[key] for key in ['cash_received', 'card', 'paytm_business', 'phonepe_business', 'notes']})
    handover.full_clean()
    handover.save()
    return handover


def handover_adjustments(shift, salesperson):
    credits = list(DebtorTransaction.objects.filter(kind='SALE', shift=shift, salesperson=salesperson).select_related('debtor'))
    expenses = list(Expense.objects.filter(source='SHIFT_CASH', shift=shift, salesperson=salesperson))
    return {'credits': credits, 'expenses': expenses, 'totals': {
        'credit_sales': sum((entry.amount for entry in credits), Decimal('0.00')),
        'expenses': sum((entry.amount for entry in expenses), Decimal('0.00'))}}


def unlocked_staff_shift(shift, salesperson):
    shift = Shift.objects.select_for_update().get(pk=shift.pk)
    if Handover.objects.filter(shift=shift, salesperson=salesperson).exists():
        raise ValidationError('This salesperson\'s handover is already saved. Linked credit sales and shift-cash expenses are locked.')
    return shift, staff_shift_sales(shift, salesperson)


def check_adjustment_limit(shift, salesperson, amount, gross):
    totals = handover_adjustments(shift, salesperson)['totals']
    from .operations import digital_totals,cash_adjustment
    digital=sum((digital_totals(shift,salesperson) or {}).values())
    allocated=totals['credit_sales']+totals['expenses']+amount+digital
    if allocated>gross or allocated>gross+cash_adjustment(shift,salesperson):
        raise ValidationError('Credit, expenses and digital collections exceed sales or cash remaining after returns.')



def check_debtor_date(debtor, date):
    latest = debtor.transactions.order_by('-date').first()
    if latest and date < latest.date:
        raise ValidationError('Enter transactions in date order. The latest entry for this debtor is on ' + str(latest.date) + '.')


@transaction.atomic
def create_debtor(values, recorded_by):
    debtor = Debtor(**{key: values[key] for key in ['name', 'phone', 'address', 'active']})
    debtor.full_clean()
    debtor.save()
    opening = Handover._meta.get_field('expected_sales').clean(values.get('opening_balance') or Decimal('0.00'), None)
    if opening > 0:
        entry = DebtorTransaction(debtor=debtor, kind='OPENING', amount=opening,
            date=values['opening_date'], reference='OPEN-' + uuid4().hex[:20], recorded_by=recorded_by,
            notes='Opening amount owed when the debtor account was created.')
        entry.full_clean()
        entry.save()
    return debtor


@transaction.atomic
def save_credit_sale(debtor, values, recorded_by):
    from .numbering import document_number
    values=dict(values)
    values['reference']=values.get('reference') or document_number('CR')
    debtor = Debtor.objects.select_for_update().get(pk=debtor.pk)
    if not debtor.active:
        raise ValidationError('This debtor is inactive. Repayments are allowed, but new credit sales are not.')
    shift, summary = unlocked_staff_shift(values['shift'], values['salesperson'])
    entry = DebtorTransaction(debtor=debtor, kind='SALE', date=shift.date, shift=shift,
        recorded_by=recorded_by, **{key: values[key] for key in ['salesperson', 'amount', 'reference', 'notes']})
    detail_fields=['vehicle_number','fuel_product','quantity','saved_rate']
    for key in detail_fields:
        if key in values:setattr(entry,key,values[key])
    supplied=[bool(entry.fuel_product),entry.quantity is not None,entry.saved_rate is not None]
    if any(supplied):
        if not all(supplied):raise ValidationError('Enter product, quantity and rate together.')
        expected=(entry.quantity*entry.saved_rate).quantize(Decimal('0.01'),rounding='ROUND_HALF_UP')
        if expected!=entry.amount:raise ValidationError('Credit amount must equal quantity times saved rate.')
        if entry.kind=='SALE':
            assigned=[r for r in entry.shift.readings.select_related('nozzle__tank') if r.salesperson_id==entry.salesperson_id and r.nozzle.tank.fuel==entry.fuel_product]
            if not assigned or any(r.unit_price!=entry.saved_rate for r in assigned):raise ValidationError('Use this shift product saved rate.')
            existing=DebtorTransaction.objects.filter(kind='SALE',shift=entry.shift,salesperson=entry.salesperson,fuel_product=entry.fuel_product)
            used=sum((e.quantity or Decimal('0') for e in existing),Decimal('0'))
            if used+entry.quantity>sum((r.litres_sold for r in assigned),Decimal('0')):raise ValidationError('Credit litres exceed assigned sold litres.')
    entry.full_clean()
    check_debtor_date(debtor, entry.date)
    check_adjustment_limit(shift, entry.salesperson, entry.amount, summary['amount'])
    entry.save()
    return entry


@transaction.atomic
def save_lube_sale(values, recorded_by):
    from .numbering import document_number
    from .operations import lube_stock
    values=dict(values); values['reference']=values.get('reference') or document_number('LS')
    product=LubeProduct.objects.select_for_update().get(pk=values['product'].pk)
    available=lube_stock(product)
    if available is not None and values['quantity']>available:raise ValidationError('Lube sale quantity exceeds available inventory.')
    shift = Shift.objects.select_for_update().get(pk=values['shift'].pk)
    if Handover.objects.filter(shift=shift, salesperson=values['salesperson']).exists():
        raise ValidationError('This salesperson\'s handover is already saved. Lube sales for that handover are locked.')
    readings = list(shift.readings.all())
    if len(readings) != 8 or any(r.unit_price is None or r.salesperson_id is None for r in readings):
        raise ValidationError('Record a complete, priced fuel shift before adding lube sales.')
    if not LubeProduct.objects.filter(pk=values['product'].pk, active=True).exists():
        raise ValidationError('Choose an active lube product.')
    if not values['salesperson'].active:
        raise ValidationError('Choose an active salesperson.')
    entry = LubeSale(recorded_by=recorded_by, **values)
    entry.full_clean()
    entry.save()
    return entry


@transaction.atomic
def save_debtor_payment(debtor, values, recorded_by):
    from .numbering import document_number
    values=dict(values);values['reference']=values.get('reference') or document_number('RP')
    debtor = Debtor.objects.select_for_update().get(pk=debtor.pk)
    entry = DebtorTransaction(debtor=debtor, kind='PAYMENT', recorded_by=recorded_by,
        **{key: values[key] for key in ['date', 'amount', 'reference', 'payment_method', 'received_by', 'notes']})
    entry.full_clean()
    check_debtor_date(debtor, entry.date)
    if not ManagerProfile.objects.filter(pk=entry.received_by_id, active=True).exists():
        raise ValidationError('Select an active receiving manager.')
    if entry.amount > debtor.balance:
        raise ValidationError('Repayment cannot exceed the outstanding balance of Rs ' + str(debtor.balance) + '.')
    entry.save()
    return entry


@transaction.atomic
def save_expense(values, recorded_by):
    from .numbering import document_number
    values=dict(values);values['voucher']=values.get('voucher') or document_number('EX')
    entry = Expense(recorded_by=recorded_by, **values)
    entry.full_clean()
    if entry.source == 'SHIFT_CASH':
        shift, summary = unlocked_staff_shift(entry.shift, entry.salesperson)
        check_adjustment_limit(shift, entry.salesperson, entry.amount, summary['amount'])
    entry.save()
    return entry


@transaction.atomic
def save_salary(person, month, base_salary, user):
    from .models import SalaryRecord, SalaryDeduction, Salesperson
    from datetime import timedelta
    month = month.replace(day=1)
    if month > timezone.localdate().replace(day=1):
        raise ValidationError('Future salary months are not allowed.')
    person = Salesperson.objects.select_for_update().get(pk=person.pk)
    if SalaryRecord.objects.filter(salesperson=person, month=month).exists():
        raise ValidationError('Salary is already recorded for this person and month.')
    if SalaryRecord.objects.filter(salesperson=person, month__gt=month).exists():
        raise ValidationError('Record salaries in month order.')
    end = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
    receipts = list(Handover.objects.filter(salesperson=person, shift__date__lt=end,
        salary_deduction__isnull=True).select_related('shift'))
    shortages = [(h, -h.variance - sum((r.amount for r in h.shortage_recoveries.all() if not r.voided), Decimal('0.00'))) for h in receipts if h.variance < 0]
    shortages = [(h, amount) for h, amount in shortages if amount > 0]
    deduction = sum((amount for h, amount in shortages), Decimal('0.00'))
    if deduction > base_salary:
        raise ValidationError('Pending shortages exceed this salary. Resolve the balance before saving; no negative salary is recorded.')
    record = SalaryRecord(salesperson=person, month=month, base_salary=base_salary,
        shortage_deduction=deduction, recorded_by=user)
    record.full_clean(); record.save()
    for h, amount in shortages:
        entry = SalaryDeduction(salary=record, handover=h, amount=amount)
        entry.full_clean(); entry.save()
    return record
