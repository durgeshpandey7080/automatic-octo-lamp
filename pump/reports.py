from decimal import Decimal
from .models import ShortageRecovery, SalaryAdvance, AdvanceRecovery, SalaryPayment, ShiftDiscount, SupplierPayment, OtherIncome, CashMovement, FuelTest, BankReconciliation, Shift, Reading, LubeSale, Handover, Expense, DebtorTransaction, Tank
from .stock import stock_summary

ZERO=Decimal('0.00')
def daily_report(date):
    shifts=list(Shift.objects.filter(date=date))
    readings=list(Reading.objects.filter(shift__date=date).select_related('nozzle__tank','salesperson'))
    lubes=list(LubeSale.objects.filter(shift__date=date).select_related('salesperson'))
    receipts=list(Handover.objects.filter(shift__date=date).select_related('shift','salesperson','submitted_to'))
    expenses=list(Expense.objects.filter(date=date))
    payments=list(DebtorTransaction.objects.filter(date=date,kind='PAYMENT').select_related('debtor','received_by'))
    fuel={fuel:{'litres':ZERO,'amount':ZERO} for fuel in ['PETROL','DIESEL']}
    pairs={}
    for reading in readings:
        fuel[reading.nozzle.tank.fuel]['litres']+=reading.litres_sold
        if reading.expected_amount is not None:
            fuel[reading.nozzle.tank.fuel]['amount']+=reading.expected_amount
        if reading.salesperson_id:
            pairs[(reading.shift_id,reading.salesperson_id)]=str(reading.salesperson)
    for sale in lubes:
        pairs[(sale.shift_id,sale.salesperson_id)]=str(sale.salesperson)
    received={(h.shift_id,h.salesperson_id) for h in receipts}
    shift_map={s.pk:s for s in shifts}
    pending=[{'shift':shift_map[sid],'name':name} for (sid,pid),name in pairs.items() if (sid,pid) not in received]
    income_total=sum((e.amount for e in OtherIncome.objects.filter(shift__date=date,voided=False)),ZERO)
    transfers=list(CashMovement.objects.filter(shift__date=date,voided=False))
    testing=sum((r.testing_litres for r in readings),ZERO)
    lube_total=sum((s.amount for s in lubes),ZERO)
    totals={field:sum((getattr(h,field) for h in receipts),ZERO) for field in
        ['cash_received','card','paytm_business','phonepe_business','upi','credit_sales','expenses','expected_sales','expected_cash']}
    totals['shortage']=sum((-h.variance for h in receipts if h.variance<0),ZERO)
    totals['excess']=sum((h.variance for h in receipts if h.variance>0),ZERO)
    expense_sources=[{'name':name,'amount':sum((e.amount for e in expenses if e.source==code),ZERO)} for code,name in Expense.SOURCES]
    stocks=[]
    for tank in Tank.objects.all().order_by('fuel','name'):
        stocks.append({'tank':tank,'stock':stock_summary(tank,date), 'dip':tank.dips.filter(shift__date=date).first()})
    complete_readings=len(shifts)==2 and len(readings)==16 and all(r.unit_price is not None and r.salesperson_id for r in readings)
    discounts=list(ShiftDiscount.objects.filter(shift__date=date,voided=False).select_related('shift','salesperson','recorded_by'))
    discount_total=sum((d.amount for d in discounts),ZERO)
    gross=sum((f['amount'] for f in fuel.values()),ZERO)+lube_total+income_total
    advances=list(SalaryAdvance.objects.filter(date=date,voided=False).select_related('salesperson','account'))
    recoveries=list(AdvanceRecovery.objects.filter(date=date,voided=False))
    salary_payments=list(SalaryPayment.objects.filter(date=date,voided=False).select_related('salary__salesperson','account'))
    return {'shortage_recovered_total':sum((r.amount for r in ShortageRecovery.objects.filter(date=date,voided=False)),ZERO),'advance_paid_total':sum((a.amount for a in advances),ZERO),'advance_cleared_total':sum((a.amount for a in recoveries),ZERO),'salary_payments':salary_payments,'salary_paid_total':sum((p.amount for p in salary_payments),ZERO),'discounts':discounts,'discount_total':discount_total,'net_sales':gross-discount_total,'report_date':date,'fuel':fuel,'lube_total':lube_total,
        'gross':sum((f['amount'] for f in fuel.values()),ZERO)+lube_total+income_total,
        'income_total':income_total,'testing_litres':testing,'cash_transfers':transfers,
        'cash_in':sum((m.amount for m in transfers if m.kind!='RETURN'),ZERO),'cash_returned':sum((m.amount for m in transfers if m.kind=='RETURN'),ZERO),
        'partial_prices':any(r.unit_price is None for r in readings), 'shifts_count':len(shifts),
        'readings_count':len(readings),'pending':pending,'receipts':receipts,'totals':totals,
        'complete':complete_readings and not pending,'expense_sources':expense_sources,
        'expense_total':sum((e.amount for e in expenses),ZERO),'expenses_list':expenses,
        'payments':payments,'repayment_total':sum((p.amount for p in payments),ZERO),
        'repayment_cash':sum((p.amount for p in payments if p.payment_method=='CASH'),ZERO),
        'supplier_payments':list(SupplierPayment.objects.filter(date=date,voided=False).select_related('purchase__supplier')),
        'stocks':stocks}
