"""Optional local narration of verified summaries; no tools or ledger writes."""
import json
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import URLError
from decimal import Decimal,InvalidOperation
from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from .ageing_views import AgeDateForm
from .owner_dashboard import station_summary,peer_summary,NoRedirect

LOCAL_URL='http://ollama:11434/api/chat'
MODEL='qwen3:1.7b'

class BriefingForm(AgeDateForm):
    scope=forms.ChoiceField(choices=[('both','Both organisations'),('current','Current organisation only')])
    language=forms.ChoiceField(choices=[('English','English'),('Hindi','Hindi')])


def facts_only(summary):
    # Deliberate allowlist: never send customers, employees, notes, credentials or files.
    return {'station':summary['code'],'business_date':summary['as_of'],'checked_at':summary['checked_at'],'figures':summary['metrics'],'shifts':summary['shifts'],'readings':summary['readings'],'complete_day':summary['complete'],'close_status':summary['close_status'],'pending_digital_count':summary['pending_digital_count'],'unallocated_bank_count':summary['unallocated_bank_count'],'cash_opening_available':summary['cash_ready'],'bank_opening_available':summary['bank_ready'],'stock':[{'fuel':r['fuel'],'litres':r['litres'],'needs_review':r['warning']} for r in summary['stocks']]}


def verified_checks(facts,language):
    hindi=language=='Hindi'
    checks=[];status=[]
    def add(code,key,en,hi):checks.append({'id':code+'_'+key,'text':hi if hindi else en})
    for f in facts:
        code=f['station'];v=f['figures']
        label={'station1':'Hamara Pump Narai','station2':'Shree Govind KSK'}[code]
        status.append((f"{label}: दिन {'पूरा' if f['complete_day'] else 'अधूरा'}; {f['shifts']}/2 शिफ्ट, {f['readings']}/16 रीडिंग। बिक्री व अन्य आय Rs {v['net_sales']}." if hindi else f"{label}: {'complete' if f['complete_day'] else 'incomplete'} day; {f['shifts']}/2 shifts, {f['readings']}/16 readings. Net sales plus other income Rs {v['net_sales']}."))
        if not f['complete_day']:add(code,'day',f'{label}: Complete and review the missing shift/readings/handovers before closing the day.',f'{label}: दिन बंद करने से पहले बाकी शिफ्ट, रीडिंग और हैंडओवर पूरे करके जाँचें।')
        if not f['cash_opening_available'] or not f['bank_opening_available']:add(code,'opening',f'{label}: Review missing cash/bank opening accounts for this date; balances are provisional.',f'{label}: इस तारीख के नकद/बैंक शुरुआती खाते जाँचें; शेष राशि अभी अस्थायी है।')
        if Decimal(v['pending_digital'])>0:add(code,'digital',f"{label}: Match {f['pending_digital_count']} pending digital collections, gross Rs {v['pending_digital']}, against provider and bank evidence.",f"{label}: {f['pending_digital_count']} लंबित डिजिटल संग्रह, कुल Rs {v['pending_digital']}, का प्रदाता और बैंक प्रमाण से मिलान करें।")
        if Decimal(v['shortage_balance'])>0:add(code,'shortage',f"{label}: Review shortage Rs {v['shortage_balance']} with waiver/recovery and salary history. Do not collect it twice.",f"{label}: Rs {v['shortage_balance']} की कमी को छूट, वसूली और वेतन इतिहास से जाँचें। दोबारा वसूली न करें।")
        if Decimal(v['debt_over_30'])>0:add(code,'debt',f"{label}: Review estimated debt older than 30 days, Rs {v['debt_over_30']}. Payment terms are not configured.",f"{label}: 30 दिन से पुराने अनुमानित उधार Rs {v['debt_over_30']} की जाँच करें। भुगतान शर्तें तय नहीं हैं।")
        if f['unallocated_bank_count']:add(code,'allocation',f"{label}: Allocate {f['unallocated_bank_count']} recorded bank movements to the correct account.",f"{label}: {f['unallocated_bank_count']} बैंक लेनदेन को सही खाते से जोड़ें।")
        if any(t['needs_review'] for t in f['stock']):add(code,'stock',f'{label}: Review missing opening fuel stock or stock outside tank capacity.',f'{label}: शुरुआती ईंधन स्टॉक या टैंक क्षमता से बाहर स्टॉक की जाँच करें।')
        if Decimal(v['cash'])<0 or Decimal(v['bank'])<0:add(code,'negative',f'{label}: Review the negative recorded cash/bank balance.',f'{label}: नकद/बैंक की नकारात्मक दर्ज राशि की जाँच करें।')
    if not checks:add('both','routine','No configured exception was detected. Verify physical cash, bank evidence and tank dips before relying on recorded balances.','कोई निर्धारित अपवाद नहीं मिला। दर्ज शेष राशि पर भरोसा करने से पहले नकद, बैंक प्रमाण और टैंक डिप जाँचें।')
    return status,checks


def generate(facts,language):
    if settings.LOCAL_AI_URL!=LOCAL_URL or settings.LOCAL_AI_MODEL!=MODEL:
        raise ValueError('Local AI is not configured for the approved on-PC model. No cloud fallback is used.')
    status,checks=verified_checks(facts,language)
    ids=[c['id'] for c in checks]
    schema={'type':'object','properties':{'priority_ids':{'type':'array','items':{'type':'string','enum':ids},'minItems':1,'maxItems':min(3,len(ids))}},'required':['priority_ids'],'additionalProperties':False}
    payload={'model':MODEL,'stream':False,'think':False,'format':schema,'keep_alive':0,'options':{'temperature':0,'num_ctx':2048,'num_predict':140},'messages':[{'role':'system','content':'Rank up to three verified petrol pump operational checks by urgency. Return only the JSON priority_ids from the supplied IDs. Prefer missing records/opening balances and negative cash first, then unmatched settlements, stock exceptions, shortages and older debt. Never invent or modify a check. You have no tools.'},{'role':'user','content':json.dumps({'checks':checks},ensure_ascii=False)}]}
    request=Request(LOCAL_URL,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
    with build_opener(ProxyHandler({}),NoRedirect()).open(request,timeout=50) as response:
        raw=response.read(65537)
        if len(raw)>65536:raise ValueError('Local model returned too much text.')
        result=json.loads(raw)
    if not isinstance(result,dict) or result.get('done') is not True or result.get('done_reason')=='length':raise ValueError('Local model did not finish a response.')
    message=result.get('message',{})
    answer=message.get('content','') if isinstance(message,dict) else ''
    selected=json.loads(answer)
    if not isinstance(selected,dict) or set(selected)!={'priority_ids'}:raise ValueError('Invalid priority response.')
    ranked=selected['priority_ids']
    if not isinstance(ranked,list) or not 1<=len(ranked)<=3 or any(not isinstance(i,str) or i not in ids for i in ranked) or len(set(ranked))!=len(ranked):raise ValueError('Unverified priority was rejected.')
    lookup={c['id']:c['text'] for c in checks}
    heading='पहले ये जाँचें:' if language=='Hindi' else 'Suggested checks first:'
    text='\n'.join(status)+'\n\n'+heading+'\n'+'\n'.join(str(n)+'. '+lookup[key] for n,key in enumerate(ranked,1))
    return {'text':text,'checks':checks,'truncated':False,'model':MODEL,'generated_at':timezone.localtime()}


@login_required
@require_http_methods(['GET','POST'])
@never_cache
def briefing(request):
    if not request.user.is_superuser:raise PermissionDenied
    initial={'date':timezone.localdate(),'scope':'both','language':'English'}
    form=BriefingForm(request.POST if request.method=='POST' else None,initial=initial)
    context={'page_name':'Local AI briefing','form':form,'model':MODEL}
    status=200
    if request.method=='POST':
        if not form.is_valid():status=400
        else:
            lock='local-ai-briefing:'+settings.STATION_CODE
            if not cache.add(lock,True,timeout=65):
                form.add_error(None,'A local briefing is already running. Wait for it to finish, then retry.');status=429
            else:
                try:
                    day=form.cleaned_data['date']
                    summaries=[station_summary(day)]
                    if form.cleaned_data['scope']=='both':summaries.append(peer_summary(day,request.user))
                    facts=[facts_only(s) for s in sorted(summaries,key=lambda s:s['code'])]
                    context['facts']=facts;context['as_of']=day
                    context['answer']=generate(facts,form.cleaned_data['language'])
                except (URLError,TimeoutError,OSError,ValueError,TypeError,KeyError,InvalidOperation,DatabaseError):
                    form.add_error(None,'The local model or a requested station is unavailable, busy, or returned an invalid result. No cloud service was used. Check the Ollama container and model download, then retry.');status=503
                finally:cache.delete(lock)
    return render(request,'pump/ai_briefing.html',context,status=status)
