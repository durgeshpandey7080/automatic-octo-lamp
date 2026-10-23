"""Friendly validation before SQLite's final closed-period triggers."""
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db.models.signals import pre_save, pre_delete
from . import models as m
from .day_close import SOURCES


def guarded_dates(instance):
    for path in SOURCES[type(instance).__name__]:
        value = instance
        try:
            for part in path.split('__'):
                value = getattr(value, part) if value is not None else None
        except ObjectDoesNotExist:
            value = None
        if value is not None:
            yield value


def guard(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    dates = list(guarded_dates(instance))
    if instance.pk:
        old = sender.objects.filter(pk=instance.pk).first()
        if old:
            dates.extend(guarded_dates(old))
    if dates and m.BusinessDayClose.objects.filter(status='CLOSED', date__gte=min(dates)).exists():
        raise ValidationError('This date is in a closed period. The owner must reopen later closed days before changing it.')


for name in SOURCES:
    model = getattr(m, name)
    pre_save.connect(guard, sender=model, weak=False, dispatch_uid='close-save-' + name)
    pre_delete.connect(guard, sender=model, weak=False, dispatch_uid='close-delete-' + name)
