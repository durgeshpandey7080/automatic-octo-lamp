"""Read-only owner summaries across separate station services. No database sharing."""
import json
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import URLError
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db import transaction, DatabaseError
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from .ageing_views import AgeDateForm
from . import models as m
from .reports import daily_report
from .money_book import statement, bank_sources
from .debtor_ageing import ageing
from .owner_insights import sales_slots, stock_details, decorate

ZERO=Decimal('0.00')
METRICS=['fuel_sales','net_sales','petrol_litres','diesel_litres','lube_sales','other_income','discounts','cash','bank','debtor_balance','debt_over_30','supplier_balance','pending_digital','shortage_balance']
COUNTS=['pending_digital_count','unallocated_bank_count']
SALT='owner-summary-v1'

@transaction.atomic
def station_summary(as_of):
    report=daily_report(as_of)
    accounts=list(m.MoneyAccount.objects.filter(opening_date__lte=as_of))
    balances={kind:sum((statement(a,a.opening_date,as_of)['balance'] for a in accounts if a.kind==kind),ZERO) for kind in ['CASH','BANK']}
    debt=ageing(as_of)
    settled=m.BankReconciliation.objects.filter(voided=False,settlement_date__lte=as_of).values_list('collection_id',flat=True)
    pending=list(m.DigitalCollection.objects.filter(shift__date__lte=as_of,voided=False).exclude(pk__in=settled))
    supplier=ZERO
    for p in m.FuelPurchase.objects.filter(date__lte=as_of,voided=False).prefetch_related('payments','credit_notes'):
        supplier+=p.total-sum((r.amount for r in p.payments.all() if not r.voided and r.date<=as_of),ZERO)-sum((r.amount for r in p.credit_notes.all() if not r.voided and r.date<=as_of),ZERO)
    shortage=ZERO
    for h in m.Handover.objects.filter(shift__date__lte=as_of).prefetch_related('shortage_recoveries','salary_deduction__adjustments'):
        if h.variance>=0:continue
        waived=ZERO
        d=m.SalaryDeduction.objects.filter(handover=h,salary__created_at__date__lte=as_of).first()
        if d:
            adjustment=d.adjustments.filter(created_at__date__lte=as_of).order_by('-pk').first()
            if adjustment:waived=d.amount-adjustment.revised_amount
        returned=sum((r.amount for r in h.shortage_recoveries.all() if not r.voided and r.date<=as_of),ZERO)
        shortage+=max(-h.variance-waived-returned,ZERO)
    latest=m.Shift.objects.filter(date__lte=as_of).order_by('-date').values_list('date',flat=True).first()
    closed=m.BusinessDayClose.objects.filter(date=as_of).first()
    latest_close=m.BusinessDayClose.objects.filter(date__lte=as_of,status='CLOSED').order_by('-date').values_list('date',flat=True).first()
    values=dict(net_sales=report['net_sales'],petrol_litres=report['fuel']['PETROL']['litres'],diesel_litres=report['fuel']['DIESEL']['litres'],lube_sales=report['lube_total'],other_income=report['income_total'],discounts=report['discount_total'],cash=balances['CASH'],bank=balances['BANK'],debtor_balance=debt['total_balance'],debt_over_30=sum(debt['age_totals'][1:],ZERO),supplier_balance=supplier,pending_digital=sum((r.amount for r in pending),ZERO),shortage_balance=shortage)
    values['fuel_sales'] = sum((f['amount'] for f in report['fuel'].values()), ZERO)
    warnings=[]
    for kind in ['CASH','BANK']:
        if not any(a.kind==kind for a in accounts):warnings.append(kind.title()+' opening account is missing at this date; balance is not established.')
    if not report['complete']:warnings.append('Selected day is incomplete: two shifts, 16 readings and all handovers are required.')
    if report['partial_prices']:warnings.append('Some readings have no saved rate; sales amount is incomplete.')
    if any(b<0 for b in balances.values()):warnings.append('A recorded money balance is negative. Review the station ledger.')
    return dict(schema=2,code=settings.STATION_CODE,name=settings.STATION_NAME,as_of=as_of.isoformat(),checked_at=timezone.localtime().isoformat(),metrics={k:str(v) for k,v in values.items()},pending_digital_count=len(pending),unallocated_bank_count=sum(1 for r in bank_sources(as_of) if not r['allocation']),shifts=report['shifts_count'],readings=report['readings_count'],complete=report['complete'],warnings=warnings,latest_sale_date=latest.isoformat() if latest else None,close_status=closed.status if closed else 'NOT STARTED',latest_closed_date=latest_close.isoformat() if latest_close else None,stocks=stock_details(report, as_of),sale_slots=sales_slots(as_of),baseline_slots=sales_slots(as_of-timedelta(days=7)),cash_ready=any(a.kind=='CASH' for a in accounts),bank_ready=any(a.kind=='BANK' for a in accounts))


@require_GET
@never_cache
def summary_endpoint(request):
    try:
        data=signing.loads(request.headers.get('X-Pump-Owner-Summary',''),salt=SALT,max_age=15)
        if data['station']!=settings.STATION_CODE or data['origin'] not in {'station1','station2'} or data['origin']==settings.STATION_CODE:raise ValueError()
        as_of=date.fromisoformat(data['date'])
        if as_of>timezone.localdate():raise ValueError()
        get_user_model().objects.get(username=data['username'],is_active=True,is_superuser=True)
    except (signing.BadSignature,ValueError,TypeError,KeyError,get_user_model().DoesNotExist):
        return JsonResponse({'error':'Owner summary authentication failed.'},status=403)
    return JsonResponse(station_summary(as_of))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def peer_summary(as_of,user):
    if not settings.OWNER_SUMMARY_PEER_URL:raise ValueError('Station summary connection is not configured.')
    target='station2' if settings.STATION_CODE=='station1' else 'station1'
    token=signing.dumps({'username':user.username,'station':target,'origin':settings.STATION_CODE,'date':as_of.isoformat()},salt=SALT)
    request=Request(settings.OWNER_SUMMARY_PEER_URL,headers={'X-Pump-Owner-Summary':token,'Host':'127.0.0.1','Accept':'application/json'})
    with build_opener(ProxyHandler({}),NoRedirect()).open(request,timeout=3) as response:
        raw=response.read(262145)
        if len(raw)>262144:raise ValueError('Summary response too large.')
        result=json.loads(raw)
    if not isinstance(result,dict) or not isinstance(result.get('metrics'),dict):raise ValueError('Invalid station summary.')
    if result.get('schema')!=2 or result.get('code')!=target or result.get('as_of')!=as_of.isoformat():raise ValueError('Unexpected station summary. Update both station services together.')
    # Validate amounts before displaying or combining a peer response.
    for k in METRICS:
        number=Decimal(result['metrics'][k])
        if not number.is_finite() or abs(number)>Decimal('1e25'):raise ValueError('Invalid station amount.')
    for k in COUNTS:
        if type(result[k]) is not int or result[k]<0:raise ValueError('Invalid station count.')
    if type(result['warnings']) is not list or type(result['stocks']) is not list:raise ValueError('Invalid station summary.')
    for key in ['name','checked_at','shifts','readings','complete','close_status','latest_sale_date','latest_closed_date','cash_ready','bank_ready']:
        if key not in result:raise ValueError('Incomplete station summary.')
    validate_details(result)
    return result


def validate_details(result):
    def number(value):
        if not isinstance(value, str): raise ValueError('Invalid numeric detail.')
        amount = Decimal(value)
        if not amount.is_finite() or abs(amount) > Decimal('1e25'): raise ValueError('Invalid numeric detail.')
        return amount
    checked = datetime.fromisoformat(result['checked_at'])
    if checked.tzinfo is None: raise ValueError('Missing summary timezone.')
    for key in ('sale_slots', 'baseline_slots'):
        slots = result[key]
        if not isinstance(slots, list) or len(slots) != 2: raise ValueError('Invalid shift details.')
        if [s['number'] for s in slots] != [1, 2]: raise ValueError('Invalid shift slots.')
        for slot in slots:
            if type(slot['count']) is not int or not 0 <= slot['count'] <= 8 or type(slot['priced']) is not bool:
                raise ValueError('Invalid reading coverage.')
            for field in ('fuel_sales', 'petrol', 'diesel'):
                if number(slot[field]) < 0: raise ValueError('Negative sales detail.')
    for tank in result['stocks']:
        if number(tank['capacity']) <= 0 or number(tank['threshold']) < 0: raise ValueError('Invalid stock setup.')
        for field in ('litres', 'dip_litres', 'dip_variance', 'coverage'):
            if tank[field] is not None: number(tank[field])
        if tank['dip_date'] is not None and date.fromisoformat(tank['dip_date']) > date.fromisoformat(result['as_of']):
            raise ValueError('Future dip detail.')
        if type(tank['history_days']) is not int or not 0 <= tank['history_days'] <= 7: raise ValueError('Invalid stock history.')


@login_required
@require_GET
@never_cache
def dashboard(request):
    if not request.user.is_superuser:raise PermissionDenied
    form=AgeDateForm(request.GET or {'date':timezone.localdate()})
    context={'page_name':'Owner dashboard','form':form,'today':timezone.localdate()}
    if not form.is_valid():return render(request,'pump/owner_dashboard.html',context,status=400)
    as_of=form.cleaned_data['date'];context['as_of']=as_of
    summaries={};errors={}
    try:summaries[settings.STATION_CODE]=station_summary(as_of)
    except DatabaseError:errors[settings.STATION_CODE]='Station database is unavailable. No balance has been substituted.'
    target='station2' if settings.STATION_CODE=='station1' else 'station1'
    try:summaries[target]=peer_summary(as_of,request.user)
    except (URLError,TimeoutError,OSError,ValueError,KeyError,TypeError,InvalidOperation):errors[target]='Station summary is unavailable or owner access was not accepted. Retry after checking the station service and owner account.'
    names={s['code']:s['name'] for s in settings.STATION_LINKS}
    for summary in summaries.values(): decorate(summary, as_of)
    context['stations']=[{'code':code,'name':names.get(code,code),'data':summaries.get(code),'error':errors.get(code)} for code in ['station1','station2']]
    context['comparison_date'] = as_of-timedelta(days=7)
    context['previous_date'] = as_of-timedelta(days=1)
    context['next_date'] = as_of+timedelta(days=1) if as_of < timezone.localdate() else None
    context['review_count'] = sum(sum(slot['overdue'] for slot in s['sale_slots']) +
        int(s['close_status'] in {'SUBMITTED', 'REVIEWED'}) + sum(t['low'] or t['warning'] or t['urgent'] or t['threshold_invalid'] for t in s['stocks'])
        for s in summaries.values()) + len(errors)
    if len(summaries)==2:
        totals={k:sum((Decimal(s['metrics'][k]) for s in summaries.values()),ZERO) for k in METRICS}
        totals.update({k:sum(s[k] for s in summaries.values()) for k in COUNTS})
        context['totals']=totals
        context['money_ready']=all(s['cash_ready'] and s['bank_ready'] for s in summaries.values())
        context['sales_complete']=all(s['complete'] for s in summaries.values())
        context['cash_ready']=all(s['cash_ready'] for s in summaries.values())
        context['has_sales']=any(s['view']['has_sales'] for s in summaries.values())
        context['both_have_sales']=all(s['view']['has_sales'] for s in summaries.values())
        context['priced']=all(s['view']['priced'] for s in summaries.values())
        views=[s['view'] for s in summaries.values()]
        if all(v['compare_available'] for v in views):
            baseline=sum((v['comparison_previous'] for v in views),ZERO)
            change=(sum((v['comparison_current'] for v in views),ZERO)-baseline)/baseline*100
            context['comparison']={'percent':abs(change),'up':change>=0,'previous':baseline}
    response=render(request,'pump/owner_dashboard.html',context,status=200 if not errors else 503)
    return response
