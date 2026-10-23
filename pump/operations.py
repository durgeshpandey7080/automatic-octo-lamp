from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from .models import *

def audit(user, record, action, reason, before=None, after=None):
    AuditEvent.objects.create(actor=user,model_name=record._meta.label,object_id=record.pk,
        action=action,reason=reason,before=before or {},after=after or {})

def staff_only(user):
    if not user.is_staff: raise PermissionDenied

def validate_date(date):
    if date > timezone.localdate(): raise ValidationError('Future dates are not allowed.')

@transaction.atomic
def open_duty(data, rows, user):
    from .services import latest_shift, next_slot
    previous=latest_shift()
    validate_date(data['date'])
    if previous and (data['date'],data['number'])!=next_slot(previous):
        raise ValidationError('Open only the next consecutive shift.')
    if not previous and data['number']!=1:raise ValidationError('Start with Shift 1.')
    if Duty.objects.filter(closed_shift=None,cancelled=False).exists():raise ValidationError('Close the existing open duty first.')
    nozzles=list(Nozzle.objects.select_for_update().order_by('number'))
    if len(nozzles)!=8 or len(rows)!=8:raise ValidationError('Configure and assign all eight nozzles.')
    duty=Duty(**data,created_by=user);duty.full_clean();duty.save()
    for fuel,rate in [('PETROL',duty.petrol_price),('DIESEL',duty.diesel_price)]:
        if rate<=0:raise ValidationError('Enter positive daily fuel prices.')
        old=DailyFuelPrice.objects.filter(date=duty.date,fuel=fuel).first()
        if old and old.price_per_litre!=rate:raise ValidationError('Duty price must match the saved daily price.')
    previous_rows={r.nozzle_id:r for r in previous.readings.all()} if previous else {}
    for nozzle,row in zip(nozzles,rows):
        if not row['salesperson'].active:raise ValidationError('Select active staff.')
        if nozzle.pk in previous_rows and row['opening_litres']!=previous_rows[nozzle.pk].closing_litres:
            raise ValidationError('Opening meters must match previous closings.')
        assignment=DutyAssignment(duty=duty,nozzle=nozzle,**row);assignment.full_clean();assignment.save()
    audit(user,duty,'OPEN_DUTY','Cashier and nozzle responsibility saved.')
    return duty

@transaction.atomic
def record_fuel_test(data,user):
    from .services import staff_shift_sales, handover_adjustments
    reading=Reading.objects.select_for_update().select_related('shift','nozzle__tank').get(pk=data['reading'].pk)
    if Handover.objects.filter(shift=reading.shift).exists():raise ValidationError('Testing is locked after any handover for this shift.')
    if TankDip.objects.filter(tank=reading.nozzle.tank,shift__date__gte=reading.shift.date).exists():raise ValidationError('Testing is locked by a saved closing dip.')
    if data.get('disposition')!='RETURNED':raise ValidationError('This station returns all testing fuel to the same tank.')
    if SalesReceipt.objects.filter(reading=reading,voided=False).exists():raise ValidationError('Testing is locked after a sales receipt is issued.')
    from .numbering import document_number
    data=dict(data);data['reference']=data.get('reference') or document_number('FT')
    record=FuelTest(**data,recorded_by=user);record.full_clean()
    reading.testing_litres+=record.litres
    if record.disposition=='RETURNED':reading.returned_test_litres+=record.litres
    allocated_bulk=sum((a.quantity for a in reading.bulk_allocations.filter(voided=False)),Decimal('0'))
    if allocated_bulk>reading.litres_sold:raise ValidationError('Testing would leave bulk allocations above sold litres. Reverse the allocation first.')
    reading.full_clean();reading.save()
    summary=staff_shift_sales(reading.shift,reading.salesperson)
    adjustments=handover_adjustments(reading.shift,reading.salesperson)['totals']
    digital=digital_totals(reading.shift,reading.salesperson)
    allocated_money=sum(adjustments.values())+sum((digital or {}).values())
    if allocated_money>summary['amount'] or allocated_money>summary['amount']+cash_adjustment(reading.shift,reading.salesperson):raise ValidationError('Testing would leave credit/expenses above remaining sales.')
    allocated=sum((e.quantity or Decimal('0') for e in DebtorTransaction.objects.filter(kind='SALE',shift=reading.shift,salesperson=reading.salesperson,fuel_product=reading.nozzle.tank.fuel)),Decimal('0'))
    if allocated>summary[reading.nozzle.tank.fuel.lower()+'_litres']:raise ValidationError('Testing would leave credit-slip litres above sold litres.')
    record.save();audit(user,record,'FUEL_TEST',record.reason,after={'litres':str(record.litres),'disposition':record.disposition})
    return record

@transaction.atomic
def void_fuel_test(record,user,reason):
    staff_only(user)
    record=FuelTest.objects.select_for_update().get(pk=record.pk)
    if record.voided:raise ValidationError('Already reversed.')
    if not reason.strip():raise ValidationError('A correction reason is required.')
    reading=Reading.objects.select_for_update().select_related('nozzle__tank','shift').get(pk=record.reading_id)
    if SalesReceipt.objects.filter(reading=reading,voided=False).exists():raise ValidationError('Void the linked receipt before reversing testing.')
    if Handover.objects.filter(shift=reading.shift).exists() or TankDip.objects.filter(tank=reading.nozzle.tank,shift__date__gte=reading.shift.date).exists():
        raise ValidationError('Settled handovers and dips lock testing corrections.')
    reading.testing_litres-=record.litres
    if record.disposition=='RETURNED':reading.returned_test_litres-=record.litres
    reading.full_clean();reading.save();record.voided=True;record.save()
    audit(user,record,'REVERSE_FUEL_TEST',reason,before={'active':True},after={'active':False})


def lube_stock(product):
    if product.inventory_started_at is None:return None
    movements=product.movements.filter(voided=False)
    received=sum((m.quantity if m.kind not in ['WASTAGE','ADJUST_OUT'] else -m.quantity for m in movements),Decimal('0'))
    sold=sum((s.quantity for s in product.sales.filter(created_at__gte=product.inventory_started_at)),Decimal('0'))
    return received-sold

def cash_adjustment(shift,person):
    return sum((m.amount if m.kind!='RETURN' else -m.amount for m in CashMovement.objects.filter(shift=shift,salesperson=person,voided=False)),Decimal('0'))

def digital_totals(shift,person):
    entries=list(DigitalCollection.objects.filter(shift=shift,salesperson=person,voided=False))
    if not entries:return None
    return {key:sum((e.amount for e in entries if e.method==method),Decimal('0')) for key,method in [('card','CARD'),('paytm_business','PAYTM'),('phonepe_business','PHONEPE')]}

@transaction.atomic
def save_operation(kind,data,user):
    from .services import unlocked_staff_shift, handover_adjustments
    classes={'income':OtherIncome,'collection':DigitalCollection,'lube-stock':LubeMovement,'cash':CashMovement,'bank':BankReconciliation,'receipt':SalesReceipt}
    if kind not in classes:raise ValidationError('Unknown operation.')
    staff_only(user)
    from .numbering import document_number
    data=dict(data)
    if kind=='receipt':data['number']=document_number('BILL')
    if kind=='collection':data['number']=document_number('DC')
    if kind not in ['bank','collection','receipt']:data['reference']=document_number({'income':'OI','collection':'DC','lube-stock':'LP','cash':'CM'}[kind])
    record=classes[kind](**data,recorded_by=user)
    if kind in ['income','collection','cash']:
        shift,summary=unlocked_staff_shift(record.shift,record.salesperson)
        if kind=='income':
            validate_date(record.date)
            if record.date!=shift.date:raise ValidationError('Income date must match its shift.')
        if kind=='cash' and not record.manager.active:raise ValidationError('Select an active manager.')
        if kind=='collection':
            existing=sum((e.amount for e in DigitalCollection.objects.filter(shift=shift,salesperson=record.salesperson,voided=False)),Decimal('0'))
            adjustments=handover_adjustments(shift,record.salesperson)['totals']
            allocated=existing+record.amount+sum(adjustments.values())
            if allocated>summary['amount'] or allocated>summary['amount']+cash_adjustment(shift,record.salesperson):
                raise ValidationError('Digital collections plus credit and expenses exceed gross sales.')
        if kind=='cash' and record.kind=='RETURN':
            balance=summary['amount']-sum(handover_adjustments(shift,record.salesperson)['totals'].values())
            digital=digital_totals(shift,record.salesperson)
            if digital:balance-=sum(digital.values())
            if record.amount>balance+cash_adjustment(shift,record.salesperson):raise ValidationError('Cash return exceeds available shift cash.')
    elif kind=='lube-stock':
        product=LubeProduct.objects.select_for_update().get(pk=record.product_id)
        validate_date(record.date)
        if record.kind=='OPENING':
            if product.inventory_started_at or LubeMovement.objects.filter(product=product,kind='OPENING').exists():raise ValidationError('Opening stock already exists.')
            product.inventory_started_at=timezone.now();product.save()
        elif product.inventory_started_at is None:raise ValidationError('Set opening inventory first.')
        if record.kind!='OPENING' and record.quantity<=0:raise ValidationError('Movement quantity must be positive.')
        if record.kind=='PURCHASE' and not record.supplier.strip():raise ValidationError('Enter the purchase supplier.')
        if record.kind in ['ADJUST_IN','ADJUST_OUT'] and not record.notes.strip():raise ValidationError('Stock adjustments require a reason in notes.')
        opening=LubeMovement.objects.filter(product=product,kind='OPENING').first()
        if opening and record.date<opening.date:raise ValidationError('Date cannot precede opening inventory.')
        if record.kind in ['WASTAGE','ADJUST_OUT'] and record.quantity>lube_stock(product):raise ValidationError('Wastage exceeds stock.')
    elif kind=='bank':
        validate_date(record.settlement_date)
        if record.collection.voided:raise ValidationError('Cannot reconcile a reversed collection.')
        if record.settlement_date<record.collection.shift.date:raise ValidationError('Settlement cannot precede the collection date.')
        if record.net_received+record.fee!=record.collection.amount:raise ValidationError('Bank net received plus fee must equal collection amount.')
    elif kind=='receipt':
        if bool(record.reading)==bool(record.lube_sale):raise ValidationError('Select exactly one fuel reading or lube sale.')
        if record.reading:
            source=record.reading
            available=source.litres_sold-sum((r.quantity for r in SalesReceipt.objects.filter(reading=source,voided=False)),Decimal('0'))
            if record.quantity is None or record.quantity<=0 or record.quantity>available:raise ValidationError('Receipt quantity exceeds uninvoiced sold litres.')
            record.rate=source.unit_price
            if record.rate is None:raise ValidationError('This reading has no saved rate.')
            record.description=str(source.nozzle)
            issued=list(SalesReceipt.objects.filter(reading=source,voided=False))
            previous_qty=sum((r.quantity for r in issued),Decimal('0'))
            previous_amount=sum((r.amount for r in issued),Decimal('0.00'))
            cumulative=((previous_qty+record.quantity)*record.rate).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
            record.amount=cumulative-previous_amount
            if record.amount<=0:raise ValidationError('This quantity rounds to no additional payable amount; use a larger quantity.')
        else:
            source=record.lube_sale
            record.quantity=source.quantity;record.rate=source.unit_price;record.amount=source.amount
            record.description=source.product.name
    record.full_clean();record.save();audit(user,record,'CREATE_'+kind.upper(),'Saved through validated operation entry.')
    return record

@transaction.atomic
def reverse_operation(kind,pk,user,reason):
    staff_only(user)
    if not reason.strip():raise ValidationError('A correction reason is required.')
    classes={'income':OtherIncome,'collection':DigitalCollection,'cash':CashMovement,'receipt':SalesReceipt,'bank':BankReconciliation,'lube-stock':LubeMovement}
    if kind=='duty':
        record=Duty.objects.select_for_update().get(pk=pk)
        if record.closed_shift_id or record.cancelled:raise ValidationError('Duty is already closed or cancelled.')
        record.cancelled=True;record.save();audit(user,record,'CANCEL_DUTY',reason);return
    if kind=='testing':return void_fuel_test(FuelTest.objects.get(pk=pk),user,reason)
    if kind not in classes:raise ValidationError('This record needs a separate controlled correction.')
    record=classes[kind].objects.select_for_update().get(pk=pk)
    if record.voided:raise ValidationError('Already reversed.')
    if kind not in ['receipt','bank','lube-stock'] and Handover.objects.filter(shift=record.shift,salesperson=record.salesperson).exists():raise ValidationError('Saved handover locks corrections.')
    if kind=='collection' and BankReconciliation.objects.filter(collection=record,voided=False).exists():raise ValidationError('Reconciled collections cannot be reversed.')
    if kind=='lube-stock' and record.kind=='OPENING':raise ValidationError('Opening inventory cannot be reversed. Record an audited stock adjustment instead.')
    record.voided=True;record.save()
    if kind=='lube-stock' and lube_stock(record.product)<0:raise ValidationError('Reversal would leave negative lube stock.')
    if kind=='cash':
        from .services import staff_shift_sales,handover_adjustments
        gross=staff_shift_sales(record.shift,record.salesperson)['amount']
        adjustments=handover_adjustments(record.shift,record.salesperson)['totals']
        digital=digital_totals(record.shift,record.salesperson)
        if gross+cash_adjustment(record.shift,record.salesperson)-sum(adjustments.values())-sum((digital or {}).values())<0:raise ValidationError('Reversal would leave negative expected cash.')
    if kind=='income':
        from .services import staff_shift_sales,handover_adjustments
        total=staff_shift_sales(record.shift,record.salesperson)['amount']
        adjustments=handover_adjustments(record.shift,record.salesperson)['totals']
        digital=digital_totals(record.shift,record.salesperson)
        allocated=sum(adjustments.values())+sum((digital or {}).values())
        if allocated>total or allocated>total+cash_adjustment(record.shift,record.salesperson):raise ValidationError('Reversal would leave collections/adjustments above sales.')
    audit(user,record,'REVERSE_'+kind.upper(),reason,before={'active':True},after={'active':False})
