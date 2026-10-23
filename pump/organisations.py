from secrets import token_urlsafe
from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

class PortalLoginView(LoginView):
    def get_success_url(self):
        return '/organisations/'

class PortalMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        if settings.STATION_CODE != 'station1' and not request.user.is_authenticated and request.path_info not in ['/sso/consume/', '/sso/logout/', '/owner-summary/']:
            return redirect(settings.PORTAL_URL + '/login/')
        return self.get_response(request)

@login_required
def organisations(request):
    if settings.STATION_CODE != 'station1':
        return redirect(settings.PORTAL_URL + '/organisations/')
    return render(request, 'pump/organisations.html', {'choices': settings.STATION_LINKS, 'page_name': 'Choose organisation'})

@login_required
@require_POST
def select_organisation(request):
    choice = next((s for s in settings.STATION_LINKS if s['code'] == request.POST.get('organisation')), None)
    if not choice:
        return HttpResponseForbidden('Unknown organisation.')
    if choice['code'] == settings.STATION_CODE:
        return redirect('entry')
    # Access is limited to the existing owner administrator in this local prototype.
    if not request.user.is_superuser:
        return HttpResponseForbidden('Organisation access requires the owner administrator.')
    ticket = signing.dumps({'username':request.user.username, 'station':choice['code'],
        'nonce':token_urlsafe(32), 'language':request.LANGUAGE_CODE}, salt='organisation-login')
    return render(request, 'pump/organisation_transfer.html', {'ticket':ticket,
        'action':choice['url']+'sso/consume/'})

@csrf_exempt
@require_POST
def consume_ticket(request):
    try:
        payload = signing.loads(request.POST.get('ticket', ''), salt='organisation-login', max_age=30)
        if payload['station'] != settings.STATION_CODE:
            raise ValueError()
        if not cache.add('sso:'+payload['nonce'], True, timeout=60):
            raise ValueError()
        user = get_user_model().objects.get(username=payload['username'], is_active=True, is_superuser=True)
    except (signing.BadSignature, ValueError, KeyError, get_user_model().DoesNotExist):
        return HttpResponseForbidden('Organisation sign-in expired. Choose the organisation again.')
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    from .interface_language import language_cookie
    code=payload.get('language','en')
    return language_cookie(redirect('entry'),code if code in {'en','hi'} else 'en',request)


@require_POST
def portal_logout(request):
    if not request.user.is_authenticated:
        return redirect(settings.PORTAL_URL + '/login/')
    username = request.user.username
    target = 'station2' if settings.STATION_CODE == 'station1' else 'station1'
    ticket = signing.dumps({'username':username, 'station':target}, salt='organisation-logout')
    logout(request)
    target_url = settings.PORTAL_URL + ('/station2/' if target == 'station2' else '/')
    return render(request, 'pump/organisation_transfer.html', {'ticket':ticket,
        'action':target_url+'sso/logout/'})

@csrf_exempt
@require_POST
def consume_logout(request):
    try:
        payload = signing.loads(request.POST.get('ticket',''), salt='organisation-logout', max_age=30)
        if payload['station'] != settings.STATION_CODE:
            raise ValueError()
    except (signing.BadSignature, ValueError, KeyError):
        return HttpResponseForbidden('Sign-out expired. Please sign out again.')
    if request.user.is_authenticated and request.user.username == payload['username']:
        logout(request)
    return redirect(settings.PORTAL_URL + '/login/')
