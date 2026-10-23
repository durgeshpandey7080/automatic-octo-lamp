from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.utils import timezone
from .models import BusinessDayClose, StaffAccess, AuditEvent
from .day_close import transition, review_data
from .access import can_manage, role_for


class CloseForm(forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    reason = forms.CharField(required=False, max_length=500, widget=forms.Textarea(attrs={'rows': 2}),
        help_text='Required for owner self-review, closing with unresolved exceptions, or reopening.')


@login_required
def day_close(request):
    form = CloseForm(request.POST or request.GET or {'date': timezone.localdate()})
    context = {'page_name': 'Approve daily close', 'form': form, 'can_review': can_manage(request.user)}
    if form.is_valid():
        date = form.cleaned_data['date']
        if request.method == 'POST':
            try:
                transition(date, request.POST.get('action'), request.user, form.cleaned_data['reason'])
            except ValidationError as exc:
                form.add_error(None, '; '.join(exc.messages))
            except IntegrityError:
                form.add_error(None, 'The day changed or is locked. Refresh and review its status.')
            except OperationalError:
                form.add_error(None, 'Another entry may be saving. Refresh and retry after it finishes; no closing was completed by this request.')
            else:
                messages.success(request, 'Daily closing status updated. No differences were erased.')
                from django.urls import reverse
                return redirect(reverse('day_close') + '?date=' + date.isoformat())
        if date <= timezone.localdate():
            report, issues, snapshot, digest = review_data(date)
            day = BusinessDayClose.objects.filter(date=date).first()
            context.update(day=day, report=report, issues=issues, current_snapshot=snapshot,
                changed=bool(day and day.fingerprint and day.fingerprint != digest),
                history=AuditEvent.objects.filter(model_name='pump.BusinessDayClose', object_id=day.pk).select_related('actor').order_by('-pk') if day else [])
        else:
            form.add_error('date', 'Choose today or a past business date.')
    return render(request, 'pump/day_close.html', context)


class AccessForm(forms.Form):
    user = forms.ModelChoiceField(queryset=get_user_model().objects.filter(is_superuser=False, is_active=True).order_by('username'))
    role = forms.ChoiceField(choices=StaffAccess._meta.get_field('role').choices)
    active = forms.BooleanField(required=False, initial=True, label='Allow this user to access this station')


@login_required
def staff_access(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden('Only the owner can assign station roles.')
    form = AccessForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = form.cleaned_data['user']
            record, created = StaffAccess.objects.get_or_create(user=user, defaults={'role': form.cleaned_data['role']})
            before = {'role': record.role, 'active': record.active}
            record.role, record.active = form.cleaned_data['role'], form.cleaned_data['active']
            record.save()
            # Managers need staff-only operational service access, but assigned roles cannot enter Django admin.
            user.is_staff = record.active and record.role == 'MANAGER'
            user.save(update_fields=['is_staff'])
            AuditEvent.objects.create(actor=request.user, model_name='pump.StaffAccess', object_id=record.pk,
                action='assign', reason='Owner assigned local station access', before=before,
                after={'role': record.role, 'active': record.active, 'username': user.username})
        messages.success(request, 'Station access saved. This applies only to the selected organisation.')
        return redirect('staff_access')
    users = [{'username': u.username, 'role': role_for(u)} for u in get_user_model().objects.order_by('username')]
    return render(request, 'pump/staff_access.html', {'page_name': 'Staff permissions', 'form': form, 'access_users': users})
