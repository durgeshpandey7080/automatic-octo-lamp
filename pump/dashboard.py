from datetime import timedelta
from decimal import Decimal
from .models import ShiftDiscount, Shift, Reading, LubeSale, OtherIncome, Handover, Tank
from .stock import stock_summary

ZERO=Decimal('0')
def dashboard_graphics(end):
    start=end-timedelta(days=6)
    days={start+timedelta(days=i):{'date':start+timedelta(days=i),'petrol':ZERO,'diesel':ZERO,'revenue':ZERO,'shifts':0,'partial':False} for i in range(7)}
    for shift in Shift.objects.filter(date__gte=start,date__lte=end):days[shift.date]['shifts']+=1
    for row in Reading.objects.filter(shift__date__gte=start,shift__date__lte=end).select_related('shift','nozzle__tank'):
        day=days[row.shift.date];day[row.nozzle.tank.fuel.lower()]+=row.litres_sold
        if row.expected_amount is None:day['partial']=True
        else:day['revenue']+=row.expected_amount
    for sale in LubeSale.objects.filter(shift__date__gte=start,shift__date__lte=end).select_related('shift'):days[sale.shift.date]['revenue']+=sale.amount
    for income in OtherIncome.objects.filter(shift__date__gte=start,shift__date__lte=end,voided=False).select_related('shift'):days[income.shift.date]['revenue']+=income.amount
    for discount in ShiftDiscount.objects.filter(shift__date__gte=start,shift__date__lte=end,voided=False).select_related('shift'):days[discount.shift.date]['revenue']-=discount.amount
    volume_max=max([max(d['petrol'],d['diesel']) for d in days.values()]+[ZERO])
    revenue_max=max([d['revenue'] for d in days.values()]+[ZERO])
    for d in days.values():
        d['petrol_height']=d['petrol']/volume_max*100 if volume_max else ZERO
        d['diesel_height']=d['diesel']/volume_max*100 if volume_max else ZERO
        d['revenue_height']=d['revenue']/revenue_max*100 if revenue_max else ZERO
    receipts=list(Handover.objects.filter(shift__date=end))
    methods=[('cash_received','Cash submitted','cash'),('paytm_business','Paytm Business','paytm'),('phonepe_business','PhonePe Business','phonepe'),('card','Card / POS','card'),('upi','Earlier unsplit UPI','legacy')]
    collections=[{'label':label,'value':sum((getattr(h,field) for h in receipts),ZERO),'color':color} for field,label,color in methods]
    collected=sum((c['value'] for c in collections),ZERO)
    for c in collections:c['percent']=c['value']/collected*100 if collected else ZERO
    tanks=[]
    for tank in Tank.objects.all().order_by('fuel','name'):
        stock=stock_summary(tank,end)
        ratio=(stock['expected']/tank.capacity_litres*100) if stock else None
        tanks.append({'tank':tank,'stock':stock,'percent':ratio,
            'fill':min(Decimal('100'),max(ZERO,ratio)) if ratio is not None else ZERO,
            'low':ratio is not None and ratio<=20})
    return {'graph_days':list(days.values()),'volume_max':volume_max,'revenue_max':revenue_max,
        'has_graph_data':any(d['shifts'] for d in days.values()),
        'graph_start':start,'graph_end':end,'collection_parts':collections,'collected_total':collected,
        'collection_receipts':len(receipts),'tank_graphics':tanks}
