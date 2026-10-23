from decimal import Decimal
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied,ObjectDoesNotExist
from django.db import IntegrityError
from django.forms import modelform_factory
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from .models import Supplier,FuelPurchase,SupplierPayment,SupplierCredit,FuelDelivery
from .suppliers import save_purchase,save_supplier_entry,reverse_supplier_entry

@login_required
def suppliers(request):
 if not request.user.is_staff:raise PermissionDenied
 accounts=list(Supplier.objects.prefetch_related('purchases__payments','purchases__credit_notes'))
 invoices=FuelPurchase.objects.select_related('supplier','delivery__tank').prefetch_related('payments','credit_notes')
 return render(request,'pump/suppliers.html',{'page_name':'Supplier accounts','suppliers':accounts,'purchases':invoices[:100],
  'total_due':sum((s.outstanding for s in accounts),Decimal('0.00'))})

@login_required
def supplier_detail(request,pk):
 if not request.user.is_staff:raise PermissionDenied
 supplier=get_object_or_404(Supplier,pk=pk)
 return render(request,'pump/supplier_detail.html',{'page_name':'Supplier account','supplier':supplier,
  'purchases':supplier.purchases.select_related('delivery__tank').prefetch_related('payments','credit_notes')})

@login_required
def supplier_add(request,kind):
 if not request.user.is_staff:raise PermissionDenied
 configs={'supplier':(Supplier,['name','phone','address','active'],'Add supplier'),
  'purchase':(FuelPurchase,['supplier','delivery','date','supplier_invoice','invoiced_litres','unit_cost','freight','notes'],'Link fuel purchase invoice'),
  'payment':(SupplierPayment,['purchase','date','amount','method','external_reference','notes'],'Record supplier payment'),
  'credit':(SupplierCredit,['purchase','date','supplier_credit_reference','amount','reason'],'Record supplier credit note')}
 if kind not in configs:
  from django.http import Http404
  raise Http404
 model,fields,title=configs[kind]
 Form=modelform_factory(model,fields=fields,widgets={'date':forms.DateInput(attrs={'type':'date'})} if 'date' in fields else {})
 initial={'date':timezone.localdate()}
 for key in ['supplier','delivery','purchase']:
  value=request.GET.get(key,'')
  if value.isdigit() and len(value)<=18:initial[key]=value
 if kind=='purchase' and initial.get('delivery'):
  delivery=FuelDelivery.objects.filter(pk=initial['delivery']).first()
  if delivery:initial.update(date=delivery.date,supplier_invoice=delivery.invoice,invoiced_litres=delivery.litres)
 form=Form(request.POST or None,initial=initial)
 if 'purchase' in form.fields:form.fields['purchase'].queryset=FuelPurchase.objects.filter(voided=False)
 if kind=='purchase':
  form.fields['supplier'].queryset=Supplier.objects.filter(active=True)
  form.fields['freight'].label='Freight billed by supplier (Rs)'
  form.fields['invoiced_litres'].help_text='Quantity billed by the supplier; actual received litres remain on the delivery record.'
 if request.method=='POST' and form.is_valid():
  try:
   if kind=='supplier':
    record=form.save()
    from .operations import audit
    audit(request.user,record,'CREATE_SUPPLIER','Supplier profile created.')
   elif kind=='purchase':record=save_purchase(form.cleaned_data,request.user)
   else:record=save_supplier_entry(kind,form.cleaned_data,request.user)
  except (ValidationError,IntegrityError) as exc:form.add_error(None,'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'Duplicate invoice or transaction reference. Review existing records.')
  else:
   messages.success(request,'Saved '+str(getattr(record,'number',record.pk)))
   return redirect('supplier_detail',pk=record.pk if kind=='supplier' else (record.supplier_id if kind=='purchase' else record.purchase.supplier_id))
 return render(request,'pump/ledger_form.html',{'page_name':'Supplier accounts','form':form,'title':title,'back_url':'suppliers',
  'description':'This organisation only. Internal numbers are generated on save.',
  'guidance':{'supplier':'Create the actual supplier account. Existing free-text delivery names are not automatically converted into debts.',
   'purchase':'Links an existing delivery without adding stock again. Invoice total = billed litres × cost + supplier-billed freight. Delivery shortage does not automatically reduce the payable. External supplier invoice number remains manual. Tax is disabled. Shift discounts apply to sales, not supplier purchase invoices.',
   'payment':'Enter a payment already made. Partial payments are supported; overpayment is rejected. This records payment only and does not transfer money. Do not also record it as an operating expense or shift deduction.',
   'credit':'Use an actual supplier-issued credit note, for example an agreed delivery shortage credit. Stock is unchanged. Credits cannot exceed the unpaid balance; refunds/advances are not supported.'}[kind],
  'button':'Save'})

@login_required
def supplier_reverse(request,kind,pk):
 if not request.user.is_staff:raise PermissionDenied
 class ReasonForm(forms.Form):reason=forms.CharField(max_length=500,widget=forms.Textarea)
 form=ReasonForm(request.POST or None)
 if request.method=='POST' and form.is_valid():
  try:reverse_supplier_entry(kind,pk,request.user,form.cleaned_data['reason'])
  except (ValidationError,ObjectDoesNotExist) as exc:form.add_error(None,'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'Record not found.')
  else:
   messages.success(request,'Correction saved; the original record and reason are retained.')
   return redirect('suppliers')
 return render(request,'pump/ledger_form.html',{'page_name':'Supplier accounts','title':'Reverse supplier entry','form':form,'back_url':'suppliers','button':'Save reversal','description':'No stock quantity will be changed.'})
