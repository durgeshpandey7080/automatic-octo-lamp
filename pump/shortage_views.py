import uuid
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import IntegrityError,OperationalError
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Handover,ShortageRecovery
from .payroll_views import PaymentForm
from .shortages import receive,reverse_receipt,collectible

class ReceiptForm(PaymentForm):
    handover=forms.ModelChoiceField(queryset=Handover.objects.select_related('shift','salesperson'))
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['handover'].label_from_instance=lambda h:f'{h.shift.date} / shift {h.shift.number} / {h.salesperson} / recoverable Rs {collectible(h)}'

@login_required
def recoveries(request):
    if not request.user.is_staff:raise PermissionDenied
    form=ReceiptForm(request.POST if request.method=='POST' else None,initial={'date':timezone.localdate(),'request_id':uuid.uuid4()})
    if request.method=='POST':
        if not request.user.is_superuser:raise PermissionDenied
        if form.is_valid():
            d=form.cleaned_data
            try:receive(d['handover'].pk,d['account'].pk,d['date'],d['amount'],d['reference'],d['notes'],d['request_id'],request.user)
            except (ValidationError,IntegrityError,OperationalError) as exc:form.add_error(None,'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'Record changed or is busy. Refresh and retry.')
            else:
                messages.success(request,'Shortage receipt recorded once. Linked salary deduction adjusted automatically.')
                return redirect('shortage_recoveries')
    return render(request,'pump/shortages.html',{'page_name':'Shortage recovery','form':form,'entries':ShortageRecovery.objects.select_related('handover__salesperson','account','salary').order_by('-pk')[:100]})

@login_required
@require_POST
def reverse(request,pk):
    if not request.user.is_superuser:raise PermissionDenied
    get_object_or_404(ShortageRecovery,pk=pk)
    try:reverse_receipt(pk,request.POST.get('reason',''),request.user)
    except (ValidationError,IntegrityError,OperationalError) as exc:messages.error(request,'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'Record changed or is busy. Refresh and retry.')
    else:messages.success(request,'Erroneous receipt reversed with history preserved. No actual money moved.')
    return redirect('shortage_recoveries')
