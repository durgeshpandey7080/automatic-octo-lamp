from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from .models import NumberSeries

@transaction.atomic
def document_number(kind):
    year=timezone.localdate().year
    prefix='HPN' if settings.STATION_CODE=='station1' else 'SGK'
    key=f'{kind}-{year}'
    series,_=NumberSeries.objects.get_or_create(key=key)
    NumberSeries.objects.filter(pk=series.pk).update(last_number=F('last_number')+1)
    series.refresh_from_db()
    return f'{prefix}/{kind}/{year}/{series.last_number:06d}'
