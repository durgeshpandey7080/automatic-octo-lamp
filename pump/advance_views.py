import uuid
from decimal import Decimal
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import IntegrityError,OperationalError
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import SalaryAdvance,AdvanceRecovery,SalaryRecord,Salesperson
from .payroll_views import PaymentForm
from .advances import record_advance,apply_advance,reverse_advance


class AdvanceForm(PaymentForm):
    employee=forms.ModelChoiceField(queryset=Salesperson.objects.filter(active=True))


class RecoveryForm(forms.Form):
    advance=forms.ModelChoiceField(queryset=SalaryAdvance.objects.filter(voided=False))
    salary=forms.ModelChoiceField(queryset=SalaryRecord.objects.select_related('salesperson'))
    date=forms.DateField(widget=forms.DateInput(attrs={'type':'date'}))
    amount=forms.DecimalField(min_value=Decimal('0.01'),max_digits=22,decimal_places=2)
    reason=forms.CharField(min_length=10,max_length=500)
    request_id=forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['advance'].label_from_instance=lambda a:f'{a.number} / {a.salesperson} / remaining Rs {a.remaining_amount}'
        self.fields['salary'].label_from_instance=lambda s:f'{s.salesperson} / {s.month:%b %Y} / outstanding Rs {s.outstanding_salary}'


@login_required
def staff_advances(request):
    if not request.user.is_staff:raise PermissionDenied
    advance_form=AdvanceForm(prefix='advance',initial={'date':timezone.localdate(),'request_id':uuid.uuid4()})
    recovery_form=RecoveryForm(prefix='recovery',initial={'date':timezone.localdate(),'request_id':uuid.uuid4()})
    if request.method=='POST':
        if not request.user.is_superuser:raise PermissionDenied
        action=request.POST.get('action')
        if action not in ['advance','recovery']:raise PermissionDenied
        form=AdvanceForm(request.POST,prefix='advance') if action=='advance' else RecoveryForm(request.POST,prefix='recovery')
        if action=='advance':advance_form=form
        else:recovery_form=form
        if form.is_valid():
            d=form.cleaned_data
            try:
                if action=='advance':record_advance(d['employee'].pk,d['account'].pk,d['date'],d['amount'],d['reference'],d['notes'],d['request_id'],request.user)
                else:apply_advance(d['advance'].pk,d['salary'].pk,d['date'],d['amount'],d['reason'],d['request_id'],request.user)
            except (ValidationError,IntegrityError,OperationalError) as exc:form.add_error(None,'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'Record changed or is busy. Refresh and retry.')
            else:
                messages.success(request,'Advance recorded once.' if action=='advance' else 'Advance linked to salary. No second cash/bank outflow created.')
                return redirect('staff_advances')
    return render(request,'pump/advances.html',{'page_name':'Staff advances','advance_form':advance_form,'recovery_form':recovery_form,'entries':SalaryAdvance.objects.select_related('salesperson','account').prefetch_related('recoveries__salary').order_by('-pk')[:100]})


@login_required
@require_POST
def advance_reverse(request,kind,pk):
    if not request.user.is_superuser:raise PermissionDenied
    if kind not in ['advance','recovery']:raise PermissionDenied
    get_object_or_404(SalaryAdvance if kind=='advance' else AdvanceRecovery,pk=pk)
    try:reverse_advance(kind,pk,request.POST.get('reason',''),request.user)
    except (ValidationError,IntegrityError,OperationalError) as exc:messages.error(request,'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'Record changed or is busy. Refresh and retry.')
    else:messages.success(request,'Erroneous record reversed with history preserved. No actual money moved.')
    return redirect('staff_advances')
