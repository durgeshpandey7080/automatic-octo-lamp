import uuid
from decimal import Decimal
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, OperationalError
from django.shortcuts import get_object_or_404, redirect, render
from .models import SalaryDeduction, Shift, Salesperson
from .salary_adjustments import adjust_shortage, remaining


class AdjustmentForm(forms.Form):
    revised = forms.DecimalField(label='Revised shortage deduction (Rs)',min_value=0,max_digits=22,decimal_places=2)
    reason = forms.CharField(min_length=10,max_length=500,widget=forms.Textarea(attrs={'rows':3}))
    expected = forms.DecimalField(widget=forms.HiddenInput,max_digits=22,decimal_places=2)
    request_id = forms.UUIDField(widget=forms.HiddenInput)


@login_required
def salary_adjust(request, pk):
    if not request.user.is_superuser:
        raise PermissionDenied
    row=get_object_or_404(SalaryDeduction.objects.select_related('salary__salesperson','handover__shift'),pk=pk)
    form=AdjustmentForm(request.POST if request.method=='POST' else None,initial={'revised':remaining(row),'expected':remaining(row),'request_id':uuid.uuid4()})
    if request.method=='POST' and form.is_valid():
        try:
            adjust_shortage(row.pk,form.cleaned_data['revised'],form.cleaned_data['expected'],form.cleaned_data['request_id'],form.cleaned_data['reason'],request.user)
        except (ValidationError,IntegrityError,OperationalError) as exc:
            form.add_error(None,'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'The record changed or is busy. Refresh and retry.')
        else:
            messages.success(request,'Salary adjustment recorded. No cash was received or salary payment made.')
            return redirect('salaries')
    return render(request,'pump/ledger_form.html',{'page_name':'Salary adjustment','title':f'Adjust shortage: {row.salary.salesperson}', 'description':f'Original deduction Rs {row.amount}; current deduction Rs {remaining(row)}.', 'guidance':'This changes salary due only. It does not correct a cash handover, record extra cash, pay a refund or alter a closed daily report. To undo an adjustment, enter the earlier deduction amount with a new reason.','form':form,'back_url':'salaries','button':'Save audited adjustment'})


class DiscountForm(forms.Form):
    amount=forms.DecimalField(label='Discount (Rs)',min_value=Decimal('0.01'),max_digits=22,decimal_places=2)
    reason=forms.CharField(min_length=10,max_length=500,widget=forms.Textarea(attrs={'rows':3}))
    request_id=forms.UUIDField(widget=forms.HiddenInput)


@login_required
def discount_add(request, shift_id, person_id):
    if not request.user.is_superuser:
        raise PermissionDenied
    shift=get_object_or_404(Shift,pk=shift_id)
    person=get_object_or_404(Salesperson,pk=person_id)
    form=DiscountForm(request.POST if request.method=='POST' else None,initial={'request_id':uuid.uuid4()})
    if request.method=='POST' and form.is_valid():
        from .discounts import save_discount
        try:
            save_discount(shift,person,form.cleaned_data['amount'],form.cleaned_data['reason'],form.cleaned_data['request_id'],request.user)
        except (ValidationError,IntegrityError,OperationalError) as exc:
            form.add_error(None,'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'The shift changed or is busy. Refresh and retry.')
        else:
            messages.success(request,'Discount saved once. Tax remains disabled.')
            return redirect('shift_workspace')
    return render(request,'pump/ledger_form.html',{'page_name':'Discount','title':f'Approve discount: {person}', 'description':str(shift),'guidance':'Owner approval only. A flat rupee discount reduces salesperson dues, not litres or saved rates. Record before handover. Credit and digital allocations must still fit the net sales. Tax is disabled.','form':form,'back_url':'shift_workspace','button':'Approve discount'})


from django.views.decorators.http import require_POST
@login_required
@require_POST
def discount_reverse(request,pk):
    if not request.user.is_superuser:
        raise PermissionDenied
    from .discounts import reverse_discount
    from .models import ShiftDiscount
    get_object_or_404(ShiftDiscount,pk=pk)
    try:
        reverse_discount(pk,request.POST.get('reason',''),request.user)
    except (ValidationError,IntegrityError,OperationalError) as exc:
        messages.error(request,'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'The record is busy. Refresh and retry.')
    else:
        messages.success(request,'Discount reversed with history preserved.')
    return redirect('shift_workspace')
