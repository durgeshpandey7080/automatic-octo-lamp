from copy import deepcopy
from django.conf import settings
from django.forms import ModelChoiceField
from django.forms.boundfield import BoundField
from django.forms.renderers import DjangoTemplates
from django.http import HttpResponseBadRequest,HttpResponseRedirect
from django.middleware.locale import LocaleMiddleware
from django.urls import reverse
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache

class InterfaceLocaleMiddleware(LocaleMiddleware):
    def process_request(self,request):
        code=request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME,'en')
        if code not in {'en','hi'}:code='en'
        translation.activate(code);request.LANGUAGE_CODE=code


def language_cookie(response,code,request):
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME,code,max_age=31536000,path='/',samesite='Lax',httponly=True,secure=request.is_secure())
    return response

@require_POST
@never_cache
def set_language(request):
    code=request.POST.get('language')
    if code not in {'en','hi'}:return HttpResponseBadRequest('Unsupported interface language.')
    target=request.POST.get('next','')
    if not target.startswith('/') or not url_has_allowed_host_and_scheme(target,allowed_hosts={request.get_host()},require_https=request.is_secure()):target=reverse('entry')
    return language_cookie(HttpResponseRedirect(target),code,request)

class LocalizedBoundField(BoundField):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.label=translation.gettext(str(self.label))
        self.help_text=translation.gettext(str(self.help_text))
    def as_widget(self,widget=None,attrs=None,only_initial=False):
        widget=deepcopy(widget or self.field.widget)
        for key in ['placeholder','aria-label','title']:
            if key in widget.attrs:widget.attrs[key]=translation.gettext(str(widget.attrs[key]))
        if hasattr(widget,'choices'):
            if isinstance(self.field,ModelChoiceField):
                # Preserve all database-backed names; only the empty prompt is interface text.
                widget.choices=[(value,translation.gettext(str(label)) if str(value)=='' else label) for value,label in widget.choices]
            else:
                def choices(rows):
                    for value,label in rows:
                        yield (value,list(choices(label))) if isinstance(label,(list,tuple)) else (value,translation.gettext(str(label)))
                widget.choices=list(choices(widget.choices))
        return super().as_widget(widget,attrs,only_initial)

class LocalizedFormRenderer(DjangoTemplates):
    bound_field_class=LocalizedBoundField
