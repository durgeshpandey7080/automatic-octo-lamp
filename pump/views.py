from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import IntegrityError
from django.shortcuts import redirect, render, get_object_or_404
from django.db.models import Sum, Count
from django.utils import timezone
from .forms import (ShiftForm, ReadingFormSet, HandoverShiftForm, HandoverForm, ManagerProfileForm,
    DebtorForm, DebtorProfileForm, CreditSaleForm, DebtorPaymentForm, ExpenseForm, LubeProductForm, LubeSaleForm)
from .models import (Nozzle, Shift, Reading, DailyFuelPrice, Salesperson, ManagerProfile, Handover,
    Debtor, DebtorTransaction, Expense, LubeProduct, LubeSale)
from .services import (latest_shift, next_slot, save_shift, staff_shift_sales, save_handover,
    handover_adjustments, create_debtor, save_credit_sale, save_debtor_payment, save_expense, save_lube_sale)

@login_required
def entry(request):
    nozzles = list(Nozzle.objects.select_related('tank').order_by('number'))
    previous = latest_shift()
    old = {r.nozzle_id: r for r in previous.readings.all()} if previous else {}
    initial = []
    for nozzle in nozzles:
        row = old.get(nozzle.pk)
        initial.append({'opening_litres': row.closing_litres} if row else {})
    date, number = next_slot(previous) if previous else (timezone.localdate(), 1)
    from .models import Duty
    open_duty=Duty.objects.filter(closed_shift=None,cancelled=False).first()
    if open_duty:
        date,number=open_duty.date,open_duty.number
        assignments={a.nozzle_id:a for a in open_duty.assignments.all()}
        initial=[{'opening_litres':assignments[n.pk].opening_litres,'salesperson':assignments[n.pk].salesperson_id} for n in nozzles if n.pk in assignments]
    prices = {p.fuel.lower() + '_price': p.price_per_litre for p in DailyFuelPrice.objects.filter(date=date)}
    if open_duty:
        prices={'petrol_price':open_duty.petrol_price,'diesel_price':open_duty.diesel_price}
    shift_form = ShiftForm(request.POST if request.method == 'POST' else None,
        initial={'date': date, 'number': number, **prices})
    fuels = {n.tank.fuel for n in nozzles}
    for fuel in ['PETROL', 'DIESEL']:
        shift_form.fields[fuel.lower() + '_price'].required = fuel in fuels
    formset = ReadingFormSet(request.POST if request.method == 'POST' else None, initial=initial)
    configured = [n.number for n in nozzles] == list(range(1, 9))
    if request.method == 'POST':
        valid_shift = shift_form.is_valid()
        valid_rows = formset.is_valid()
        if valid_shift and valid_rows:
            try:
                saved = save_shift(shift_form.cleaned_data['date'], shift_form.cleaned_data['number'],
                    [f.cleaned_data for f in formset], prices={
                        'PETROL': shift_form.cleaned_data.get('petrol_price'),
                        'DIESEL': shift_form.cleaned_data.get('diesel_price')})
            except ValidationError as exc:
                shift_form.add_error(None, ValidationError(exc.messages))
            except IntegrityError:
                shift_form.add_error(None, 'This shift was already saved. Refresh the page before continuing.')
            else:
                messages.success(request, f'Saved {saved}: all eight nozzles.')
                return redirect('entry')
    history = list(Shift.objects.prefetch_related('readings__nozzle', 'readings__salesperson', 'lube_sales__product').all()[:10])
    for shift in history:
        shift.total_litres = sum((r.litres_sold for r in shift.readings.all()), Decimal('0'))
        shift.total_due = sum((r.expected_amount for r in shift.readings.all() if r.expected_amount is not None), Decimal('0'))
        shift.lube_total = sum((sale.amount for sale in shift.lube_sales.all()), Decimal('0.00'))
        shift.total_due += shift.lube_total - sum((d.amount for d in shift.discounts.filter(voided=False)),Decimal("0.00"))
        shift.has_unpriced = any(r.unit_price is None for r in shift.readings.all())
    summary_date = previous.date if previous else timezone.localdate()
    daily_rows = list(Reading.objects.filter(shift__date=summary_date).select_related('salesperson', 'nozzle__tank'))
    daily_lubes = list(LubeSale.objects.filter(shift__date=summary_date).select_related('salesperson', 'product'))
    people = {}
    for reading in daily_rows:
        key = reading.salesperson_id
        person = people.setdefault(key, {'name': str(reading.salesperson) if key else 'Unassigned (older entry)',
            'litres': Decimal('0'), 'petrol': Decimal('0'), 'diesel': Decimal('0'),
            'lubes': Decimal('0.00'), 'amount': Decimal('0'), 'unpriced': False})
        person['litres'] += reading.litres_sold
        person[reading.nozzle.tank.fuel.lower()] += reading.litres_sold
        person['unpriced'] |= reading.expected_amount is None
        if reading.expected_amount is not None:
            person['amount'] += reading.expected_amount
    for sale in daily_lubes:
        person = people.setdefault(sale.salesperson_id, {'name': str(sale.salesperson), 'litres': Decimal('0'),
            'petrol': Decimal('0'), 'diesel': Decimal('0'), 'lubes': Decimal('0.00'), 'amount': Decimal('0'), 'unpriced': False})
        person['lubes'] += sale.amount
        person['amount'] += sale.amount
    from .models import OtherIncome, ShiftDiscount
    incomes=list(OtherIncome.objects.filter(shift__date=summary_date,voided=False))
    for income in incomes:
        if income.salesperson_id in people:people[income.salesperson_id]['amount']+=income.amount
    discounts=list(ShiftDiscount.objects.filter(shift__date=summary_date,voided=False))
    for d in discounts:
        if d.salesperson_id in people:people[d.salesperson_id]['amount']-=d.amount
    discount_total=sum((d.amount for d in discounts),Decimal('0.00'))
    income_total=sum((e.amount for e in incomes),Decimal('0.00'))
    from .dashboard import dashboard_graphics
    return render(request, 'pump/entry.html', {**dashboard_graphics(summary_date), 'shift_form': shift_form, 'formset': formset,
        'rows': list(zip(nozzles, formset)), 'configured': configured, 'history': history,
        'summary_date': summary_date, 'total_litres': sum((r.litres_sold for r in daily_rows), Decimal('0')),
        'income_total':income_total,'discount_total':discount_total,
        'total_due': income_total - discount_total + sum((r.expected_amount for r in daily_rows if r.expected_amount is not None), Decimal('0')) + sum((sale.amount for sale in daily_lubes), Decimal('0.00')),
        'petrol_litres': sum((r.litres_sold for r in daily_rows if r.nozzle.tank.fuel == 'PETROL'), Decimal('0')),
        'diesel_litres': sum((r.litres_sold for r in daily_rows if r.nozzle.tank.fuel == 'DIESEL'), Decimal('0')),
        'lube_amount': sum((sale.amount for sale in daily_lubes), Decimal('0.00')),
        'has_unpriced': any(r.unit_price is None for r in daily_rows),
        'completed_shifts': Shift.objects.filter(date=summary_date).count(),
        'people': sorted(people.values(), key=lambda p: p['name']),
        'nozzle_count': len(nozzles), 'next_date': date, 'next_number': number,
        'has_people': Salesperson.objects.filter(active=True).exists(), 'previous': previous,
        'active_prices': DailyFuelPrice.objects.filter(date=summary_date),
        'uses_petrol': 'PETROL' in fuels, 'uses_diesel': 'DIESEL' in fuels})


@login_required
def handovers(request):
    latest = latest_shift()
    data = request.GET if request.GET else ({'shift': latest.pk} if latest else None)
    selection = HandoverShiftForm(data)
    selected = selection.cleaned_data['shift'] if selection.is_valid() else None
    groups = {}
    if selected:
        saved = {h.salesperson_id: h for h in selected.handovers.select_related('submitted_to')}
        for reading in selected.readings.select_related('salesperson', 'nozzle__tank'):
            key = reading.salesperson_id
            group = groups.setdefault(key, {'person': reading.salesperson, 'litres': Decimal('0'),
                'amount': Decimal('0.00'), 'petrol': Decimal('0'), 'diesel': Decimal('0'),
                'lubes': Decimal('0.00'), 'unpriced': False, 'handover': saved.get(key)})
            group['litres'] += reading.litres_sold
            group[reading.nozzle.tank.fuel.lower()] += reading.litres_sold
            group['unpriced'] |= reading.expected_amount is None
            if reading.expected_amount is not None:
                group['amount'] += reading.expected_amount
        for sale in selected.lube_sales.select_related('salesperson'):
            group = groups.setdefault(sale.salesperson_id, {'person': sale.salesperson, 'litres': Decimal('0'),
                'petrol': Decimal('0'), 'diesel': Decimal('0'), 'lubes': Decimal('0.00'),
                'amount': Decimal('0.00'), 'unpriced': False, 'handover': saved.get(sale.salesperson_id)})
            group['lubes'] += sale.amount
            group['amount'] += sale.amount
    if selected:
        from .models import OtherIncome
        for income in OtherIncome.objects.filter(shift=selected,voided=False):
            if income.salesperson_id in groups:groups[income.salesperson_id]['amount']+=income.amount
    if selected:
        from .models import ShiftDiscount
        for discount in ShiftDiscount.objects.filter(shift=selected,voided=False):
            if discount.salesperson_id in groups:groups[discount.salesperson_id]['amount']-=discount.amount
    return render(request, 'pump/handovers.html', {'selection': selection, 'selected': selected,
        'groups': list(groups.values()), 'page_name': 'Salesperson handover'})


@login_required
def handover_detail(request, shift_id, person_id):
    shift = get_object_or_404(Shift, pk=shift_id)
    person = get_object_or_404(Salesperson, pk=person_id)
    saved = Handover.objects.select_related('submitted_to', 'recorded_by').filter(shift=shift, salesperson=person).first()
    summary = None
    source_error = None
    try:
        summary = staff_shift_sales(shift, person)
    except ValidationError as exc:
        source_error = ' '.join(exc.messages)
    form = None
    linked = handover_adjustments(shift, person)
    if saved and request.method == 'POST':
        messages.info(request, 'This handover is already recorded and was left unchanged.')
        return redirect('handover_detail', shift_id=shift.pk, person_id=person.pk)
    if not saved and summary:
        references = [f'Credit {entry.reference}: {entry.debtor}' for entry in linked['credits']]
        references += [f'Expense {entry.voucher}' for entry in linked['expenses']]
        from .operations import cash_adjustment
        form = HandoverForm(request.POST if request.method == 'POST' else None,
            instance=Handover(cash_adjustment=cash_adjustment(shift,person),shift=shift, salesperson=person, expected_sales=summary['amount'],
                notes='; '.join(references)[:1000], **linked['totals']))
        if request.method == 'POST' and form.is_valid():
            try:
                save_handover(shift, person, form.cleaned_data, request.user)
            except ValidationError as exc:
                # Preserve useful field errors when the service catches a late validation change.
                form.add_error(None, ValidationError(exc.messages))
            except IntegrityError:
                form.add_error(None, 'Handover was already recorded. Refresh to view the saved record.')
            else:
                messages.success(request, f'Handover recorded for {person}.')
                return redirect('handover_detail', shift_id=shift.pk, person_id=person.pk)
    return render(request, 'pump/handover_detail.html', {'shift': shift, 'person': person, 'summary': summary,
        'record': saved, 'source_error': source_error, 'form': form,
        'cash_adjustment': form.instance.cash_adjustment if form else (saved.cash_adjustment if saved else Decimal('0')),
        'linked': linked, 'legacy_adjustments': saved and (saved.credit_sales != linked['totals']['credit_sales']
            or saved.expenses != linked['totals']['expenses']),
        'has_managers': ManagerProfile.objects.filter(active=True).exists(), 'page_name': 'Salesperson handover'})


@login_required
def managers(request):
    profiles = list(ManagerProfile.objects.annotate(receipt_count=Count('handovers'),
        total_cash=Sum('handovers__cash_received', default=Decimal('0.00')))
    )
    cash_receipts = {row['received_by']: row for row in DebtorTransaction.objects.filter(kind='PAYMENT', payment_method='CASH')
        .values('received_by').annotate(amount=Sum('amount'), count=Count('pk'))}
    from .models import CashMovement
    for profile in profiles:
        profile.total_cash+=sum((m.amount for m in CashMovement.objects.filter(manager=profile,kind='RETURN',voided=False)),Decimal('0.00'))
        extra = cash_receipts.get(profile.pk, {})
        profile.total_cash += extra.get('amount', Decimal('0.00'))
        profile.receipt_count += extra.get('count', 0)
    return render(request, 'pump/managers.html', {'profiles': profiles, 'page_name': 'Manager profiles'})


@login_required
def manager_detail(request, manager_id):
    profile = get_object_or_404(ManagerProfile, pk=manager_id)
    receipts = profile.handovers.select_related('shift', 'salesperson', 'recorded_by')
    repayments = profile.debtor_receipts.filter(kind='PAYMENT').select_related('debtor').order_by('-date', '-pk')
    debtor_cash = repayments.filter(payment_method='CASH').aggregate(total=Sum('amount', default=Decimal('0.00')))['total']
    from .models import CashMovement
    transfers=list(CashMovement.objects.filter(manager=profile,voided=False).select_related('shift','salesperson'))
    returned=sum((m.amount for m in transfers if m.kind=='RETURN'),Decimal('0.00'))
    issued=sum((m.amount for m in transfers if m.kind!='RETURN'),Decimal('0.00'))
    return render(request, 'pump/manager_detail.html', {'profile': profile,
        'total_cash': receipts.aggregate(total=Sum('cash_received', default=Decimal('0.00')))['total'] + debtor_cash + returned,
        'cash_transfers':transfers,'cash_issued':issued,'cash_returned':returned,
        'receipt_count': receipts.count() + repayments.filter(payment_method='CASH').count(),
        'debtor_cash': debtor_cash, 'debtor_receipts': repayments[:20],
        'receipts': receipts[:20], 'page_name': 'Manager profile'})


@login_required
def manager_edit(request, manager_id=None):
    permission = 'pump.change_managerprofile' if manager_id else 'pump.add_managerprofile'
    if not request.user.has_perm(permission):
        raise PermissionDenied
    profile = get_object_or_404(ManagerProfile, pk=manager_id) if manager_id else None
    form = ManagerProfileForm(request.POST if request.method == 'POST' else None, instance=profile)
    if request.method == 'POST' and form.is_valid():
        saved = form.save()
        messages.success(request, f'Manager profile saved: {saved.name}.')
        return redirect('manager_detail', manager_id=saved.pk)
    return render(request, 'pump/manager_form.html', {'form': form, 'profile': profile, 'page_name': 'Manager profile'})


def ledger_initial(request):
    latest = latest_shift()
    initial = {'shift': latest.pk if latest else None}
    for key in ['shift', 'salesperson', 'debtor']:
        value = request.GET.get(key, '')
        if value.isdigit() and len(value) <= 18:
            initial[key] = value
    if initial['shift']:
        shift = Shift.objects.filter(pk=initial['shift']).first()
        if shift:
            initial['date'] = shift.date
    return initial


def ledger_error(form, exc):
    if isinstance(exc, ValidationError):
        form.add_error(None, ValidationError(exc.messages))
    else:
        form.add_error(None, 'This reference already exists or a related record changed. Check existing records before resubmitting.')


@login_required
def debtors(request):
    query = request.GET.get('q', '').strip()
    accounts = Debtor.objects.prefetch_related('transactions')
    if query:
        accounts = accounts.filter(name__icontains=query)
    accounts = list(accounts)
    return render(request, 'pump/debtors.html', {'accounts': accounts, 'query': query,
        'total_due': sum((account.balance for account in accounts), Decimal('0.00')), 'page_name': 'Debtor accounts'})


@login_required
def debtor_add(request):
    form = DebtorForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            account = create_debtor(form.cleaned_data, request.user)
        except (ValidationError, IntegrityError) as exc:
            ledger_error(form, exc)
        else:
            messages.success(request, f'Debtor account created: {account}.')
            return redirect('debtor_detail', debtor_id=account.pk)
    from .forms import automatic_number_fields
    automatic_number_fields(form)
    return render(request, 'pump/ledger_form.html', {'form': form, 'page_name': 'Debtor accounts',
        'title': 'Add debtor account', 'description': 'Create a customer account for fuel sold on credit.',
        'guidance': 'Opening amount owed is optional. It creates a separate opening entry and is not counted as new fuel sales.',
        'back_url': 'debtors', 'button': 'Create debtor account'})


@login_required
def debtor_detail(request, debtor_id):
    account = get_object_or_404(Debtor, pk=debtor_id)
    entries = list(account.transactions.select_related('shift', 'salesperson', 'received_by', 'recorded_by'))
    balance = Decimal('0.00')
    for entry in entries:
        balance += entry.signed_amount
        entry.running_balance = balance
    return render(request, 'pump/debtor_detail.html', {'account': account, 'entries': entries,
        'balance': balance, 'page_name': 'Debtor accounts'})


@login_required
def debtor_edit(request, debtor_id):
    account = get_object_or_404(Debtor, pk=debtor_id)
    form = DebtorProfileForm(request.POST if request.method == 'POST' else None, instance=account)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Debtor profile updated; ledger entries were preserved.')
        return redirect('debtor_detail', debtor_id=account.pk)
    from .forms import automatic_number_fields
    automatic_number_fields(form)
    return render(request, 'pump/ledger_form.html', {'form': form, 'page_name': 'Debtor accounts',
        'title': 'Edit debtor profile', 'description': str(account),
        'guidance': 'Inactive accounts cannot receive new credit sales, but existing dues can still be repaid.',
        'back_url': 'debtors', 'button': 'Save profile'})


@login_required
def credit_sale_add(request):
    form = CreditSaleForm(request.POST if request.method == 'POST' else None, initial=ledger_initial(request))
    if request.method == 'POST' and form.is_valid():
        data = dict(form.cleaned_data)
        debtor = data.pop('debtor')
        try:
            entry = save_credit_sale(debtor, data, request.user)
        except (ValidationError, IntegrityError) as exc:
            ledger_error(form, exc)
        else:
            messages.success(request, 'Credit sale recorded and linked to the salesperson handover.')
            return redirect('debtor_detail', debtor_id=entry.debtor_id)
    from .forms import automatic_number_fields
    automatic_number_fields(form)
    return render(request, 'pump/ledger_form.html', {'form': form, 'page_name': 'Debtor accounts',
        'title': 'Record credit fuel sale', 'description': 'Link the customer\'s credit slip to a recorded shift and salesperson.',
        'guidance': 'Record this before cash handover. The business date comes from the shift. This allocates part of existing fuel sales to a debtor; it does not add fuel sales again.',
        'back_url': 'debtors', 'button': 'Save credit sale', 'add_debtor_link': True})


@login_required
def debtor_payment_add(request, debtor_id):
    account = get_object_or_404(Debtor, pk=debtor_id)
    form = DebtorPaymentForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            save_debtor_payment(account, form.cleaned_data, request.user)
        except (ValidationError, IntegrityError) as exc:
            ledger_error(form, exc)
        else:
            messages.success(request, 'Repayment recorded. The customer\'s outstanding balance has been reduced.')
            return redirect('debtor_detail', debtor_id=account.pk)
    from .forms import automatic_number_fields
    automatic_number_fields(form)
    return render(request, 'pump/ledger_form.html', {'form': form, 'page_name': 'Debtor accounts',
        'title': 'Record debtor repayment', 'description': f'{account} · Outstanding Rs {account.balance:.2f}',
        'guidance': 'This repays an existing debt. Do not enter it again as current-shift fuel collections. Cash repayments also appear in the receiving manager\'s cash total.',
        'back_url': 'debtors', 'button': 'Save repayment'})


@login_required
def expenses(request):
    entries = Expense.objects.select_related('shift', 'salesperson', 'recorded_by')
    return render(request, 'pump/expenses.html', {'entries': entries[:100], 'entry_count': entries.count(),
        'total': entries.aggregate(total=Sum('amount', default=Decimal('0.00')))['total'],
        'page_name': 'Expenses'})


@login_required
def expense_add(request):
    form = ExpenseForm(request.POST if request.method == 'POST' else None, initial=ledger_initial(request))
    if request.method == 'POST' and form.is_valid():
        try:
            save_expense(form.cleaned_data, request.user)
        except (ValidationError, IntegrityError) as exc:
            ledger_error(form, exc)
        else:
            messages.success(request, 'Expense saved. Shift-cash expenses are included in the linked handover.')
            return redirect('expenses')
    from .forms import automatic_number_fields
    automatic_number_fields(form)
    return render(request, 'pump/ledger_form.html', {'form': form, 'page_name': 'Expenses',
        'title': 'Record expense', 'description': 'Keep the voucher, category and payment source together.',
        'guidance': 'Choose Salesperson shift cash only when paid out of that shift\'s cash; select its shift, salesperson and matching business date. For other payment sources, leave shift and salesperson blank. Saved records are read-only.',
        'back_url': 'expenses', 'button': 'Save expense'})


@login_required
def lubes(request):
    sales = LubeSale.objects.select_related('product', 'shift', 'salesperson')
    return render(request, 'pump/lubes.html', {'products': LubeProduct.objects.all(),
        'sales': sales[:100], 'total_sales': sum((sale.amount for sale in sales), Decimal('0.00')),
        'page_name': 'Lube sales'})


@login_required
def lube_product_edit(request, product_id=None):
    product = get_object_or_404(LubeProduct, pk=product_id) if product_id else None
    form = LubeProductForm(request.POST if request.method == 'POST' else None, instance=product)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Lube product saved. Existing sale rates were preserved.')
        return redirect('lubes')
    from .forms import automatic_number_fields
    automatic_number_fields(form)
    return render(request, 'pump/ledger_form.html', {'form': form, 'page_name': 'Lube sales',
        'title': 'Edit lube product' if product else 'Add lube product',
        'description': 'Each product and pack size has its own price and sales unit.',
        'guidance': 'For example, record different oil grades or pack sizes as separate products. Price changes apply to new sales only. A used sales unit cannot be changed.',
        'back_url': 'lubes', 'button': 'Save lube product'})


@login_required
def lube_sale_add(request):
    form = LubeSaleForm(request.POST if request.method == 'POST' else None, initial=ledger_initial(request))
    if request.method == 'POST' and form.is_valid():
        try:
            save_lube_sale(form.cleaned_data, request.user)
        except (ValidationError, IntegrityError) as exc:
            ledger_error(form, exc)
        else:
            messages.success(request, 'Lube sale saved and included in the salesperson\'s handover amount.')
            return redirect('lubes')
    products = [{'id': str(p.pk), 'price': str(p.selling_price), 'unit': p.get_unit_display()}
        for p in LubeProduct.objects.filter(active=True)]
    from .forms import automatic_number_fields
    automatic_number_fields(form)
    return render(request, 'pump/ledger_form.html', {'form': form, 'page_name': 'Lube sales',
        'title': 'Record lube sale', 'description': 'Choose the product, quantity, rate and salesperson.',
        'guidance': 'Record the fuel shift first, then lube sales, then credit/expenses and handover. The product price fills automatically; confirm the actual selling rate. Lube quantities use the product\'s unit, not nozzle litres.',
        'back_url': 'lubes', 'button': 'Save lube sale', 'lube_products': products})


@login_required
def salaries(request):
    from .models import SalaryRecord
    if not request.user.is_staff:
        raise PermissionDenied
    records = SalaryRecord.objects.select_related('salesperson').prefetch_related('deductions__handover__shift','deductions__adjustments__recorded_by','payments__account','payments__recorded_by','advance_recoveries')
    from .shortages import collectible
    pending = []
    for h in Handover.objects.filter(salary_deduction__isnull=True).select_related('shift','salesperson'):
        h.pending_shortage = collectible(h)
        if h.pending_shortage > 0:pending.append(h)
    return render(request, 'pump/salaries.html', {'page_name': 'Salaries', 'records': records,
        'pending': pending, 'pending_total': sum((h.pending_shortage for h in pending), Decimal('0.00'))})

@login_required
def salary_add(request):
    from .forms import SalaryForm
    from .services import save_salary
    if not request.user.is_staff:
        raise PermissionDenied
    form = SalaryForm(request.POST or None, initial={'month': timezone.localdate().replace(day=1)})
    if request.method == 'POST' and form.is_valid():
        try:
            save_salary(form.cleaned_data['salesperson'], form.cleaned_data['month'], form.cleaned_data['base_salary'], request.user)
        except (ValidationError, IntegrityError) as exc:
            form.add_error(None, '; '.join(exc.messages) if isinstance(exc, ValidationError) else 'Salary or shortage already recorded. Refresh and retry.')
        else:
            messages.success(request, 'Salary recorded with linked shortage deductions. No payment has been transferred.')
            return redirect('salaries')
    from .forms import automatic_number_fields
    automatic_number_fields(form)
    return render(request, 'pump/ledger_form.html', {'page_name': 'Salaries', 'title': 'Record monthly salary',
        'description': 'Fixed salary minus saved cash shortages.', 'back_url': 'salaries', 'form': form,
        'guidance': 'All undeducted shortages through the selected month are included automatically, including earlier pending shortages. Excess cash does not cancel shortages. Saved salary records are read-only. This records salary due, not payment.',
        'button': 'Save salary calculation'})


@login_required
def tank_stock(request):
    from .models import Tank, FuelDelivery, TankDip
    from .stock import stock_summary
    rows = [{'tank':tank,'stock':stock_summary(tank),'dip':tank.dips.select_related('shift').first()} for tank in Tank.objects.all().order_by('fuel','name')]
    return render(request,'pump/tank_stock.html',{'page_name':'Tank stock','rows':rows,
        'deliveries':FuelDelivery.objects.select_related('tank')[:100],
        'dips':TankDip.objects.select_related('tank','shift')[:100]})

@login_required
def stock_add(request, kind):
    from .forms import TankOpeningForm, FuelDeliveryForm, TankDipForm
    from .stock import save_stock_entry
    configs = {'opening':(TankOpeningForm,'Set opening stock','Opening stock is measured at the START of the chosen date, before that day sales and deliveries. Earlier sales are excluded. Set it once per tank.'),
        'delivery':(FuelDeliveryForm,'Record fuel delivery','Enter actual litres received into this tank and a unique invoice reference. Record deliveries before saving that day dip.'),
        'dip':(TankDipForm,'Record closing dip','End-of-day dip requires completed Shift 2. Enter calibrated stock in LITRES, not centimetres or millimetres. Physical minus calculated stock is shown as variance; dips do not reset book stock.')}
    if kind not in configs:
        from django.http import Http404
        raise Http404
    cls,title,guidance = configs[kind]
    form=cls(request.POST or None,initial={'date':timezone.localdate()})
    if request.method=='POST' and form.is_valid():
        try:
            save_stock_entry(kind,form.cleaned_data,request.user)
        except ValidationError as exc:
            form.add_error(None,'; '.join(exc.messages))
        except IntegrityError:
            form.add_error(None,'This stock record already exists. Refresh and check the saved records.')
        else:
            messages.success(request,'Tank stock entry saved.')
            return redirect('tank_stock')
    return render(request,'pump/ledger_form.html',{'page_name':'Tank stock','title':title,
        'description':'Stock belongs only to the current organisation.','back_url':'tank_stock',
        'form':form,'guidance':guidance,'button':'Save stock entry'})


@login_required
def daily_closing(request):
    from django import forms
    from .reports import daily_report
    class DateFilter(forms.Form):
        date=forms.DateField(widget=forms.DateInput(attrs={'type':'date'}))
        def clean_date(self):
            date=self.cleaned_data['date']
            if date>timezone.localdate():
                raise forms.ValidationError('Choose today or a past business date.')
            return date
    last=latest_shift()
    form=DateFilter(request.GET or {'date':last.date if last else timezone.localdate()})
    context={'page_name':'Daily closing','date_form':form}
    if form.is_valid():
        context.update(daily_report(form.cleaned_data['date']))
    return render(request,'pump/daily_closing.html',context,status=200 if form.is_valid() else 400)


@login_required
def shift_workspace(request):
    last=latest_shift()
    data=request.GET or ({'shift':last.pk} if last else None)
    form=HandoverShiftForm(data)
    shift=None; rows=[]; total=Decimal('0.00'); pending=0
    if form.is_valid():
        shift=form.cleaned_data['shift']
        ids=set(shift.readings.exclude(salesperson=None).values_list('salesperson_id',flat=True))
        ids.update(shift.lube_sales.values_list('salesperson_id',flat=True))
        receipts={h.salesperson_id:h for h in shift.handovers.select_related('submitted_to')}
        for person in Salesperson.objects.filter(pk__in=ids).order_by('name'):
            row={'person':person,'receipt':receipts.get(person.pk)}
            try:
                summary=staff_shift_sales(shift,person)
                adjustments=handover_adjustments(shift,person)
                row['sales']=summary
                row['credit']=adjustments['totals']['credit_sales']
                row['expenses']=adjustments['totals']['expenses']
                total+=summary['amount']
            except ValidationError:
                row['unavailable']=True
            if not row['receipt']:pending+=1
            rows.append(row)
    return render(request,'pump/shift_workspace.html',{'page_name':'Shift workspace',
        'shift_form':form,'shift':shift,'work_rows':rows,'workspace_total':total,'pending_count':pending,'workspace_discounts':shift.discounts.select_related('salesperson','recorded_by').all() if shift else []})
