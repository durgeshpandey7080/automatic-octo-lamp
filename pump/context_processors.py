from django.conf import settings

def station(request):
    return {'software_name': 'Pandey Petrol Pump', 'station_name': settings.STATION_NAME, 'station_code': settings.STATION_CODE,
            'station_links': settings.STATION_LINKS}
