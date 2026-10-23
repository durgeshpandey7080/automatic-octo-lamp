from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction, IntegrityError
from django.shortcuts import render, redirect
from django.utils import timezone
from .access import can_manage
from .models import TankQualityObservation, AuditEvent


class QualityForm(forms.ModelForm):
    class Meta:
        model = TankQualityObservation
        fields = ['tank', 'date', 'kind', 'delivery', 'observed_at', 'observed_density', 'temperature_c', 'density_15c', 'correction_source', 'water_mm', 'notes']
        widgets = {'date':forms.DateInput(attrs={'type':'date'}), 'observed_at':forms.DateTimeInput(attrs={'type':'datetime-local'})}
        labels = {'observed_density':'Observed density (kg/m³)', 'temperature_c':'Observed temperature (°C)', 'density_15c':'Density at 15°C (kg/m³), if available', 'water_mm':'Measured water dip (mm)'}
        help_texts = {'density_15c':'Enter only a verified instrument/table result. The software does not calculate this.',
            'observed_at':'Actual measurement time in station local time; entry time is recorded separately.'}


@login_required
def quality_register(request):
    form = QualityForm(initial={'date':timezone.localdate()})
    if request.method == 'POST':
        if not can_manage(request.user):
            raise PermissionDenied
        try:
            if request.POST.get('action') == 'reverse':
                if not request.user.is_superuser:
                    raise PermissionDenied
                reason = request.POST.get('reason','').strip()
                if len(reason) < 10:
                    raise ValidationError('Give a reversal explanation of at least 10 characters.')
                with transaction.atomic():
                    row = TankQualityObservation.objects.select_for_update().get(pk=request.POST.get('record_id'),voided=False)
                    row.voided=True
                    row.save(update_fields=['voided'])
                    AuditEvent.objects.create(actor=request.user,model_name='pump.TankQualityObservation',object_id=row.pk,action='reverse',reason=reason,after={'voided':True})
                messages.success(request,'Observation reversed with history retained.')
                return redirect('quality_register')
            form = QualityForm(request.POST)
            if form.is_valid():
                with transaction.atomic():
                    row=form.save(commit=False)
                    row.recorded_by=request.user
                    row.save()
                    AuditEvent.objects.create(actor=request.user,model_name='pump.TankQualityObservation',object_id=row.pk,action='record',reason='Actual tank measurement recorded',after={'tank':str(row.tank),'date':row.date.isoformat(),'water_mm':str(row.water_mm)})
                messages.success(request,'Observation recorded. This is not an automated quality certification.')
                return redirect('quality_register')
        except ValidationError as exc:
            form.add_error(None,'; '.join(exc.messages))
        except IntegrityError:
            form.add_error(None,'Duplicate observation, locked date or concurrent change. Check existing records.')
        except (TankQualityObservation.DoesNotExist,ValueError,TypeError):
            form.add_error(None,'Observation not found.')
    return render(request,'pump/quality_register.html',{'page_name':'Tank quality register','form':form,'can_record_quality':can_manage(request.user),
        'observations':TankQualityObservation.objects.select_related('tank','delivery','recorded_by').order_by('-date','-pk')[:100]})
