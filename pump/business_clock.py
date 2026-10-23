"""Shared schedule. It never rewrites stored business dates."""
from datetime import date, datetime, time, timedelta
from django.utils import timezone


def local_time(instant):
    if timezone.is_naive(instant):
        raise ValueError('An aware timestamp is required.')
    return timezone.localtime(instant)


def business_date_at(instant):
    local = local_time(instant)
    return local.date() + timedelta(days=local.time() >= time(22))


def shift_period(day, number):
    if type(day) is not date or type(number) is not int or number not in (1, 2):
        raise ValueError('A business date and shift 1 or 2 are required.')
    if number == 1:
        start = datetime.combine(day-timedelta(days=1), time(22))
        end = datetime.combine(day, time(10))
    else:
        start = datetime.combine(day, time(10))
        end = datetime.combine(day, time(22))
    return timezone.make_aware(start), timezone.make_aware(end)


def shift_deadline(day, number):
    return shift_period(day, number)[1] + timedelta(minutes=30)
