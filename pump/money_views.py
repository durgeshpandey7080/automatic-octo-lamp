import csv
from datetime import timedelta
from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from .models import MoneyAccount, MoneyTransfer, BankAllocation, AuditEvent, DigitalCollection
from .money_book import statement, bank_sources, save_transfer, assign_bank
from .access import can_manage


class PeriodForm(forms.Form):
    start = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    end = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))

    def clean(self):
        data = super().clean()
        if data.get('start') and data.get('end'):
            if data['start'] > data['end'] or data['end'] > timezone.localdate():
                raise forms.ValidationError('Choose an ordered date range ending today or earlier.')
        return data


class AccountForm(forms.ModelForm):
    class Meta:
        model = MoneyAccount
        fields = ['name', 'kind', 'opening_date', 'opening_balance']
        widgets = {'opening_date': forms.DateInput(attrs={'type': 'date'})}

    def clean(self):
        data = super().clean()
        if data.get('opening_date') and data['opening_date'] > timezone.localdate():
            raise forms.ValidationError('Future opening dates are not allowed.')
        if data.get('kind') == 'CASH' and data.get('opening_balance', 0) < 0:
            raise forms.ValidationError('Physical opening cash cannot be negative.')
        return data


class TransferForm(forms.ModelForm):
    class Meta:
        model = MoneyTransfer
        fields = ['date', 'source', 'destination', 'amount', 'external_reference', 'notes']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}


class BankAssignmentForm(forms.Form):
    source = forms.ChoiceField(label='Existing bank movement')
    account = forms.ModelChoiceField(queryset=MoneyAccount.objects.filter(kind='BANK'))
    allow_reassign = forms.BooleanField(required=False, label='Correct an existing assignment (owner only)')
    correction_reason = forms.CharField(required=False, max_length=500, label='Owner correction explanation')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['source'].choices = [('', 'Select a recorded movement')] + [
            (r['kind'] + ':' + str(r['source_id']), str(r['date']) + ' · ' + r['label'] + ' · ₹ ' + str(r['amount']) + ' · ' + (r['allocation'].account.name if r['allocation'] else 'Unassigned'))
            for r in bank_sources(timezone.localdate())]

    def clean(self):
        data = super().clean()
        source = data.pop('source', None)
        if source:
            data['kind'], source_id = source.split(':')
            data['source_id'] = int(source_id)
        return data


def safe_cell(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value


@login_required
def money_book(request):
    end = timezone.localdate()
    period = PeriodForm(request.GET or {'start': end.replace(day=1), 'end': end})
    account_form = AccountForm(prefix='account')
    transfer_form = TransferForm(prefix='transfer', initial={'date': end})
    assignment_form = BankAssignmentForm(prefix='bank')
    if request.method == 'POST':
        if not can_manage(request.user):
            raise PermissionDenied
        action = request.POST.get('action')
        try:
            if action == 'account':
                if not request.user.is_superuser:
                    raise PermissionDenied
                account_form = AccountForm(request.POST, prefix='account')
                if account_form.is_valid():
                    with transaction.atomic():
                        account = account_form.save(commit=False)
                        account.recorded_by = request.user
                        account.save()
                        AuditEvent.objects.create(actor=request.user, model_name='pump.MoneyAccount', object_id=account.pk,
                            action='opening', reason='Owner entered actual opening balance', after={'name': account.name, 'opening_balance': str(account.opening_balance)})
                    messages.success(request, 'Account and opening balance saved. Existing earlier movements are excluded from this opening baseline.')
                    return redirect('money_book')
            elif action == 'transfer':
                transfer_form = TransferForm(request.POST, prefix='transfer')
                if transfer_form.is_valid():
                    save_transfer(transfer_form.cleaned_data, request.user)
                    messages.success(request, 'Transfer saved once: an outflow from one account and an inflow to the other.')
                    return redirect('money_book')
            elif action == 'assign':
                assignment_form = BankAssignmentForm(request.POST, prefix='bank')
                if assignment_form.is_valid():
                    assign_bank(**assignment_form.cleaned_data, user=request.user)
                    messages.success(request, 'Existing bank movement assigned. No new income or expense was created.')
                    return redirect('money_book')
            elif action == 'reverse':
                if not request.user.is_superuser:
                    raise PermissionDenied
                reason = request.POST.get('reason', '').strip()
                if len(reason) < 10:
                    raise ValidationError('Explain the reversal in at least 10 characters.')
                with transaction.atomic():
                    record = MoneyTransfer.objects.select_for_update().get(pk=request.POST.get('transfer_id'), voided=False)
                    record.voided = True
                    record.save(update_fields=['voided'])
                    AuditEvent.objects.create(actor=request.user, model_name='pump.MoneyTransfer', object_id=record.pk,
                        action='reverse', reason=reason, after={'voided': True})
                messages.success(request, 'Transfer reversed with its history retained.')
                return redirect('money_book')
            else:
                messages.error(request, 'Unknown money-book action.')
        except (ValidationError, IntegrityError) as exc:
            messages.error(request, '; '.join(exc.messages) if isinstance(exc, ValidationError) else 'Duplicate reference, closed date or concurrent change. Review saved records.')
        except (MoneyTransfer.DoesNotExist, ValueError, TypeError):
            messages.error(request, 'Transfer not found.')
    books = []
    unassigned = []
    if period.is_valid():
        start, end = period.cleaned_data['start'], period.cleaned_data['end']
        for account in MoneyAccount.objects.order_by('kind', 'name'):
            if account.opening_date <= end:
                books.append(statement(account, max(start, account.opening_date), end))
        unassigned = [r for r in bank_sources(end) if not r['allocation']]
        if request.GET.get('export') == 'csv':
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = 'attachment; filename="cash-bank-book.csv"'
            response.write('\ufeff')
            writer = csv.writer(response)
            writer.writerow(['Account', 'Date', 'Description', 'Reference', 'Incoming', 'Outgoing', 'Balance'])
            for book in books:
                writer.writerow([safe_cell(book['account'].name), max(start, book['account'].opening_date), 'Opening for selected period', '', '', '', book['opening']])
                for row in book['rows']:
                    writer.writerow([safe_cell(book['account'].name), row['date'], safe_cell(row['label']), safe_cell(row['reference']), row['incoming'], row['outgoing'], row['balance']])
            return response
    return render(request, 'pump/money_book.html', {'page_name': 'Cash & bank book', 'period': period,
        'books': books, 'unassigned': unassigned, 'account_form': account_form,
        'transfer_form': transfer_form, 'assignment_form': assignment_form,
        'can_manage_money': can_manage(request.user), 'transfers': MoneyTransfer.objects.select_related('source', 'destination').order_by('-date', '-pk')[:100],
        'pending_digital': DigitalCollection.objects.filter(voided=False).exclude(reconciliations__voided=False).select_related('shift')[:100]})
