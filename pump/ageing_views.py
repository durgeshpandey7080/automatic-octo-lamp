import csv
from django import forms
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from .debtor_ageing import ageing
from .money_views import safe_cell


class AgeDateForm(forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={'type':'date'}))
    def clean_date(self):
        date = self.cleaned_data['date']
        if date > timezone.localdate():
            raise forms.ValidationError('Choose today or a past date.')
        return date


@login_required
def debtor_ageing(request):
    form = AgeDateForm(request.GET or {'date': timezone.localdate()})
    context = {'page_name': 'Debtor ageing', 'form':form}
    if form.is_valid():
        date = form.cleaned_data['date']
        context.update(ageing(date), as_of=date)
        if request.GET.get('export') == 'csv':
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = 'attachment; filename="debtor-ageing.csv"'
            response.write('\ufeff')
            writer = csv.writer(response)
            writer.writerow(['Customer','As of','0-30 days','31-60 days','61-90 days','Over 90 days','Total','Oldest unpaid date'])
            for row in context['accounts']:
                writer.writerow([safe_cell(row['debtor'].name),date,*row['buckets'],row['balance'],row['oldest']])
            return response
    return render(request,'pump/debtor_ageing.html',context,status=200 if form.is_valid() else 400)
