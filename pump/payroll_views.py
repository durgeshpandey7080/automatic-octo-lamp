import uuid
from decimal import Decimal
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import IntegrityError,OperationalError
from django.shortcuts import get_object_or_404,render,redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import SalaryRecord,SalaryPayment,MoneyAccount
from .payroll import record_payment,reverse_payment


class PaymentForm(forms.Form):
    account=forms.ModelChoiceField(queryset=MoneyAccount.objects.all())
    date=forms.DateField(widget=forms.DateInput(attrs={'type':'date'}))
    amount=forms.DecimalField(min_value=Decimal('0.01'),max_digits=22,decimal_places=2)
    reference=forms.CharField(required=False,max_length=100,label='Bank transaction reference / cash receipt reference')
    notes=forms.CharField(min_length=10,max_length=500,widget=forms.Textarea(attrs={'rows':3}))
    request_id=forms.UUIDField(widget=forms.HiddenInput)


@login_required
def salary_payment(request,pk):
    if not request.user.is_superuser:raise PermissionDenied
    salary=get_object_or_404(SalaryRecord.objects.select_related('salesperson'),pk=pk)
    form=PaymentForm(request.POST if request.method=='POST' else None,initial={'date':timezone.localdate(),'request_id':uuid.uuid4()})
    if request.method=='POST' and form.is_valid():
        d=form.cleaned_data
        try:record_payment(salary.pk,d['account'].pk,d['date'],d['amount'],d['reference'],d['notes'],d['request_id'],request.user)
        except (ValidationError,IntegrityError,OperationalError) as exc:
            form.add_error(None,'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'The record changed or is busy. Refresh and retry.')
        else:
            messages.success(request,'Salary payment recorded once in the selected cash/bank account. No money was transferred by this software.')
            return redirect('salaries')
    return render(request,'pump/ledger_form.html',{'page_name':'Salary payment','title':f'Record salary payment: {salary.salesperson}','description':f'Revised due Rs {salary.adjusted_net_salary}; already paid Rs {salary.paid_amount}; outstanding Rs {salary.outstanding_salary}.','form':form,'back_url':'salaries','button':'Record salary payment','guidance':'Record money already paid. This does not send money. Select the account that paid it; bank reference required. Do not also enter an expense or transfer for the same payment. Partial payments allowed; overpayments blocked. Closed dates require owner reopening. Use Staff advances to record advances and clear them against salary. Use Shortage recovery for money returned against a shortage. Actual salary refunds remain a separate future workflow.'})


@login_required
@require_POST
def salary_payment_reverse(request,pk):
    if not request.user.is_superuser:raise PermissionDenied
    get_object_or_404(SalaryPayment,pk=pk)
    try:reverse_payment(pk,request.POST.get('reason',''),request.user)
    except (ValidationError,IntegrityError,OperationalError) as exc:
        messages.error(request,'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'Record is busy. Refresh and retry.')
    else:messages.success(request,'Payment record reversed. This does not return or move actual money.')
    return redirect('salaries')
