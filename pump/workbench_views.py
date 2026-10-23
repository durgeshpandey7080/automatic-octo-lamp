from decimal import Decimal
from django import forms
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from .models import Shift, Duty, Handover
from .reports import daily_report


class DayForm(forms.Form):
    date=forms.DateField(widget=forms.DateInput(attrs={'type':'date'}))


@login_required
def daily_workbench(request):
    form=DayForm(request.GET or {'date':timezone.localdate()})
    context={'page_name':'Daily workbench','form':form}
    if form.is_valid():
        date=form.cleaned_data['date'];report=daily_report(date)
        tabs=[]
        for number in [1,2]:
            shift=Shift.objects.filter(date=date,number=number).first()
            draft=Duty.objects.filter(date=date,number=number,cancelled=False,closed_shift=None).first()
            pending=[p for p in report['pending'] if shift and p['shift'].pk==shift.pk]
            status=('Saved' if not pending else 'Ready for handover') if shift else ('Draft duty open' if draft else 'Not entered')
            tabs.append({'number':number,'shift':shift,'status':status})
        allocation=[]
        for h in report['receipts']:
            # Explain the same identity as Handover. Bank deposits are subsequent transfers.
            allocated=h.cash_received+h.card+h.total_upi+h.credit_sales+h.expenses-h.cash_adjustment
            allocation.append({'handover':h,'allocated':allocated,'remainder':h.expected_sales-allocated})
        context.update(report=report,tabs=tabs,allocation=allocation)
    return render(request,'pump/daily_workbench.html',context)
