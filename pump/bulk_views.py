import uuid
from decimal import Decimal
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction,IntegrityError,OperationalError
from django.shortcuts import render,redirect,get_object_or_404
from django.views.decorators.http import require_POST
from .access import can_manage
from .models import Reading,BulkSaleAllocation,AuditEvent
from .numbering import document_number


@transaction.atomic
def save_bulk(reading,quantity,customer,vehicle,reason,request_id,user):
    if not can_manage(user):raise PermissionDenied
    existing=BulkSaleAllocation.objects.filter(request_id=request_id).first()
    if existing:
        if (existing.reading_id,existing.quantity,existing.customer,existing.vehicle_number,existing.reason)!=(reading.pk,quantity,customer.strip(),vehicle.strip(),reason.strip()):
            raise ValidationError('Submission reference has already been used.')
        return existing
    reading=Reading.objects.select_for_update().get(pk=reading.pk)
    if not reading.unit_price or not reading.salesperson_id:raise ValidationError('Use a priced reading with a salesperson.')
    used=sum((a.quantity for a in reading.bulk_allocations.filter(voided=False)),Decimal('0'))
    if quantity<=0 or used+quantity>reading.litres_sold:raise ValidationError('Bulk litres cannot exceed unallocated sold litres in this nozzle reading.')
    entry=BulkSaleAllocation(reading=reading,quantity=quantity,customer=customer.strip(),vehicle_number=vehicle.strip(),reason=reason.strip(),request_id=request_id,reference=document_number('BA'),recorded_by=user)
    entry.full_clean();entry.save()
    AuditEvent.objects.create(action='bulk_allocation',model_name='BulkSaleAllocation',object_id=entry.pk,reason=entry.reason,actor=user,after={'litres':str(quantity),'reading':reading.pk,'sales_added':'0'})
    return entry


class BulkForm(forms.Form):
    reading=forms.ModelChoiceField(queryset=Reading.objects.select_related('shift','nozzle','salesperson').filter(unit_price__isnull=False).order_by('-shift__date','-shift__number','nozzle__number'))
    customer=forms.CharField(max_length=100)
    vehicle=forms.CharField(max_length=30,required=False)
    quantity=forms.DecimalField(label='Bulk litres already included in this meter reading',max_digits=16,decimal_places=3,min_value=Decimal('0.001'))
    reason=forms.CharField(min_length=10,max_length=500)
    request_id=forms.UUIDField(widget=forms.HiddenInput)


@login_required
def bulk_sales(request):
    form=BulkForm(request.POST if request.method=='POST' else None,initial={'request_id':uuid.uuid4()})
    if request.method=='POST':
        if not can_manage(request.user):raise PermissionDenied
        if form.is_valid():
            try:
                d=form.cleaned_data
                save_bulk(d['reading'],d['quantity'],d['customer'],d['vehicle'],d['reason'],d['request_id'],request.user)
            except (ValidationError,IntegrityError,OperationalError) as exc:
                form.add_error(None,'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'Record changed or is busy. Refresh and retry.')
            else:
                messages.success(request,'Bulk allocation recorded. No additional sale, stock withdrawal or collection created.')
                return redirect('bulk_sales')
    return render(request,'pump/bulk_sales.html',{'page_name':'Bulk allocations','form':form,'can_add':can_manage(request.user),'entries':BulkSaleAllocation.objects.select_related('reading__shift','reading__nozzle','recorded_by').order_by('-pk')[:100]})


@login_required
@require_POST
@transaction.atomic
def bulk_reverse(request,pk):
    if not request.user.is_superuser:raise PermissionDenied
    entry=get_object_or_404(BulkSaleAllocation.objects.select_for_update(),pk=pk)
    reason=request.POST.get('reason','').strip()
    try:
        if len(reason)<10:raise ValidationError('Explain reversal in at least 10 characters.')
        if not entry.voided:
            entry.voided=True;entry.save(update_fields=['voided'])
            AuditEvent.objects.create(action='bulk_allocation_reversed',model_name='BulkSaleAllocation',object_id=entry.pk,reason=reason,actor=request.user,before={'voided':False},after={'voided':True})
    except ValidationError as exc:
        messages.error(request,'; '.join(exc.messages))
    else:messages.success(request,'Allocation reversed. Meter sales remain unchanged.')
    return redirect('bulk_sales')
