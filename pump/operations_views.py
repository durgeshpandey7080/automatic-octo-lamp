from decimal import Decimal
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied, ObjectDoesNotExist
from django.db import IntegrityError
from django.forms import modelform_factory, formset_factory
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from .models import *
from .forms import ShiftForm, automatic_number_fields
from .services import latest_shift,next_slot
from .operations import open_duty,record_fuel_test,save_operation,reverse_operation,lube_stock

CONFIGS={
 'testing':(FuelTest,['reading','litres','disposition','reason'],'Record returned testing fuel'),
 'income':(OtherIncome,['date','shift','salesperson','description','amount'],'Record other income'),
 'collection':(DigitalCollection,['shift','salesperson','method','amount','reference','terminal'],'Record digital collection'),
 'lube-stock':(LubeMovement,['product','date','kind','quantity','unit_cost','supplier','supplier_invoice','notes'],'Record lube inventory'),
 'cash':(CashMovement,['shift','salesperson','manager','kind','amount','notes'],'Record cash movement'),
 'bank':(BankReconciliation,['collection','settlement_date','bank_name','bank_reference','net_received','fee','notes'],'Reconcile bank settlement'),
 'receipt':(SalesReceipt,['reading','lube_sale','customer_name','vehicle_number','quantity'],'Issue sales receipt'),
}

@login_required
def operations_home(request):
 if not request.user.is_staff:raise PermissionDenied
 products=list(LubeProduct.objects.all())
 for product in products:
  product.stock_available=lube_stock(product)
  product.stock_low=product.stock_available is not None and product.stock_available<=product.reorder_level
 return render(request,'pump/operations.html',{'page_name':'Operations ledger',
  'open_duties':Duty.objects.filter(closed_shift=None,cancelled=False).prefetch_related('assignments__nozzle','assignments__salesperson'),
  'tests':FuelTest.objects.select_related('reading__shift','reading__nozzle').order_by('-pk')[:100],
  'credits':DebtorTransaction.objects.filter(kind='SALE').select_related('debtor').order_by('-pk')[:100],
  'incomes':OtherIncome.objects.select_related('shift','salesperson').order_by('-pk')[:100],
  'collections':DigitalCollection.objects.select_related('shift','salesperson').order_by('-pk')[:100],
  'products':products,'movements':LubeMovement.objects.select_related('product').order_by('-pk')[:100],
  'cash_movements':CashMovement.objects.select_related('shift','salesperson','manager').order_by('-pk')[:100],
  'banks':BankReconciliation.objects.select_related('collection').order_by('-pk')[:100],
  'receipts':SalesReceipt.objects.order_by('-pk')[:100],
  'audits':AuditEvent.objects.select_related('actor').order_by('-pk')[:100]})

@login_required
def duty_add(request):
 if not request.user.is_staff:raise PermissionDenied
 previous=latest_shift(); date,number=next_slot(previous) if previous else (timezone.localdate(),1)
 nozzles=list(Nozzle.objects.select_related('tank').order_by('number'))
 old={r.nozzle_id:r for r in previous.readings.all()} if previous else {}
 initial=[{'salesperson':old[n.pk].salesperson_id,'opening_litres':old[n.pk].closing_litres} if n.pk in old else {} for n in nozzles]
 class AssignmentForm(forms.Form):
  salesperson=forms.ModelChoiceField(queryset=Salesperson.objects.filter(active=True))
  opening_litres=forms.DecimalField(max_digits=16,decimal_places=3,min_value=0)
 Rows=formset_factory(AssignmentForm,extra=0,min_num=8,max_num=8,validate_min=True,validate_max=True,absolute_max=8)
 form=ShiftForm(request.POST or None,initial={'date':date,'number':number})
 form.fields['petrol_price'].required=True;form.fields['diesel_price'].required=True
 rows=Rows(request.POST or None,initial=initial)
 if request.method=='POST':
  valid=form.is_valid();valid_rows=rows.is_valid()
  if valid and valid_rows:
   try:open_duty(form.cleaned_data,[f.cleaned_data for f in rows],request.user)
   except (ValidationError,IntegrityError) as exc:form.add_error(None,'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'Duty already exists.')
   else:
    messages.success(request,'Duty opened. Closing entry will use these assignments and opening readings.')
    return redirect('operations_home')
 return render(request,'pump/duty_form.html',{'page_name':'Open duty','form':form,'formset':rows,'rows':zip(nozzles,rows)})

@login_required
def operation_add(request,kind):
 if not request.user.is_staff:raise PermissionDenied
 if kind not in CONFIGS:
  from django.http import Http404
  raise Http404
 model,fields,title=CONFIGS[kind]
 Form=modelform_factory(model,fields=fields,widgets={name:forms.DateInput(attrs={'type':'date'}) for name in ['date','settlement_date'] if name in fields})
 initial={'date':timezone.localdate(),'settlement_date':timezone.localdate()}
 for key in ['shift','salesperson','reading','collection']:
  value=request.GET.get(key,'')
  if value.isdigit() and len(value)<=18:initial[key]=value
 if initial.get('shift'):
  shift=Shift.objects.filter(pk=initial['shift']).first()
  if shift:initial['date']=shift.date
 if kind=='testing':initial['disposition']='RETURNED'
 form=Form(request.POST or None,initial=initial)
 if kind=='testing':form.fields['disposition'].choices=[('RETURNED','Returned to same tank')]
 if kind=='collection':
  form.fields['reference'].label='Bank UTR / POS transaction ID'
  form.fields['reference'].help_text='Enter the real external transaction reference; this is not a bill number.'
 if kind=='receipt':form.fields['quantity'].required=False
 if request.method=='POST' and form.is_valid():
  try:
   data=form.cleaned_data
   if kind=='testing':record=record_fuel_test(data,request.user)
   else:record=save_operation(kind,data,request.user)
  except (ValidationError,IntegrityError) as exc:form.add_error(None,'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'Duplicate number or related record conflict; refresh and check records.')
  else:
   messages.success(request,'Saved '+str(getattr(record,'number',None) or getattr(record,'reference',None) or record.pk))
   if kind=='receipt':return redirect('sales_receipt',pk=record.pk)
   return redirect('operations_home')
 return render(request,'pump/ledger_form.html',{'page_name':'Operations ledger','title':title,'form':form,'back_url':'operations_home',
  'description':'This organisation only. Existing records stay unchanged.',
  'guidance':{'testing':'All testing fuel is returned to the same tank. Record before any shift handover or closing dip. Testing reduces billable litres but not returned stock.',
   'income':'Income adds to assigned shift revenue once. If collected digitally, also record that payment transaction before handover.',
   'collection':'Saved digital transactions replace manual provider totals on the handover. Enter every digital collection for that person/shift once you use this ledger.',
   'lube-stock':'Set opening stock before purchases. Existing historical sales before inventory activation are excluded from the opening balance. Stock and cash payment for purchases are separate records.',
   'cash':'Float and office receipts increase expected shift cash. Cash returned to the manager reduces final handover cash. These are cash transfers, not sales or expenses.',
   'bank':'Net bank credit plus fee must equal the selected collection. This records a manual match, not bank verification. A fee is shown here; expense accounting is separate.',
   'receipt':'Ordinary sales receipt, not a GST tax invoice. Tax is disabled. Shift discounts are shown separately in the daily report; this item receipt remains at its saved gross rate. Select one fuel reading or lube sale. Fuel quantity cannot exceed uninvoiced sold litres.'}[kind],
  'button':'Save'})

@login_required
def operation_reverse(request,kind,pk):
 if not request.user.is_staff:raise PermissionDenied
 class ReasonForm(forms.Form):reason=forms.CharField(max_length=500,widget=forms.Textarea)
 form=ReasonForm(request.POST or None)
 if request.method=='POST' and form.is_valid():
  try:reverse_operation(kind,pk,request.user,form.cleaned_data['reason'])
  except (ValidationError,ObjectDoesNotExist) as exc:form.add_error(None,'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'Record not found.')
  else:
   messages.success(request,'Reversal recorded. Original entry and audit history retained.')
   return redirect('operations_home')
 return render(request,'pump/ledger_form.html',{'page_name':'Operations ledger','title':'Reverse record','description':'A reason is required; settled records remain locked.','form':form,'back_url':'operations_home','button':'Record reversal'})

@login_required
def sales_receipt(request,pk):
 record=get_object_or_404(SalesReceipt,pk=pk)
 return render(request,'pump/sales_receipt.html',{'page_name':'Sales receipt','receipt':record})
