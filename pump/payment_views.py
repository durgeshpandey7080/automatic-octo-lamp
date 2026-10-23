from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import render, redirect
from .access import can_manage
from .models import PaymentImportBatch, PaymentEvidence, DigitalCollection
from .payment_imports import preview_csv, commit_import, match_evidence


class PaymentUploadForm(forms.Form):
    provider = forms.ChoiceField(choices=PaymentImportBatch._meta.get_field('provider').choices)
    merchant = forms.CharField(max_length=100, help_text='Actual merchant identifier. Keep different merchant accounts separate.')
    file = forms.FileField(help_text='UTF-8 CSV, maximum 2 MB. Use the template headings and successful payments only.')


@login_required
def payment_imports(request):
    if request.GET.get('template') == 'csv':
        response = HttpResponse('reference,date,amount,status,description\n', content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="payment-import-template.csv"'
        return response
    form = PaymentUploadForm()
    if request.method == 'POST':
        if not can_manage(request.user):
            raise PermissionDenied
        try:
            action = request.POST.get('action')
            if action == 'preview':
                request.session.pop('payment_import_preview', None)
                form = PaymentUploadForm(request.POST, request.FILES)
                if form.is_valid():
                    upload = form.cleaned_data['file']
                    if upload.size > 2 * 1024 * 1024:
                        raise ValidationError('CSV limit is 2 MB.')
                    preview = preview_csv(upload.read())
                    preview.update(provider=form.cleaned_data['provider'], merchant=form.cleaned_data['merchant'])
                    request.session['payment_import_preview'] = preview
                    messages.success(request, 'Preview prepared. Confirm below to store evidence; no collections, sales or bank credits will be created.')
            elif action == 'commit':
                preview = request.session.get('payment_import_preview')
                if not preview:
                    raise ValidationError('Upload and preview the file first.')
                batch, created = commit_import(preview, preview['provider'], preview['merchant'], request.user)
                request.session.pop('payment_import_preview', None)
                messages.success(request, f"{'Imported' if created else 'Already imported'}: {batch.new_rows} new rows, {batch.duplicate_rows} duplicate rows skipped. No financial postings created.")
                return redirect('payment_imports')
            elif action == 'discard':
                request.session.pop('payment_import_preview', None)
                messages.success(request, 'Preview discarded.')
                return redirect('payment_imports')
            elif action == 'match':
                match_evidence(int(request.POST.get('evidence_id')), int(request.POST.get('collection_id')), request.user)
                messages.success(request, 'Payment evidence matched. Bank settlement remains a separate check.')
                return redirect('payment_imports')
            else:
                raise ValidationError('Unknown import action.')
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
        except (ValueError, TypeError, PaymentEvidence.DoesNotExist, DigitalCollection.DoesNotExist):
            messages.error(request, 'The selected evidence or collection was not found.')
        except IntegrityError:
            messages.error(request, 'Duplicate transaction or collection match. Refresh to see current records.')
    preview = request.session.get('payment_import_preview')
    evidence = list(PaymentEvidence.objects.select_related('collection').order_by('-pk')[:100])
    collections = {c.reference: c for c in DigitalCollection.objects.filter(voided=False, reference__in=[e.reference for e in evidence]).select_related('shift')}
    for e in evidence:
        c = collections.get(e.reference)
        e.candidate = c if c and c.method == e.provider and c.amount == e.amount and c.shift.date == e.date and (not c.terminal or c.terminal == e.merchant) else None
    return render(request, 'pump/payment_imports.html', {'page_name': 'Payment report imports', 'form': form,
        'can_manage_imports': can_manage(request.user), 'preview': preview,
        'preview_rows': preview['rows'][:100] if preview else [], 'preview_count': len(preview['rows']) if preview else 0,
        'evidence': evidence,
        'batches': PaymentImportBatch.objects.select_related('imported_by').order_by('-pk')[:20]})
