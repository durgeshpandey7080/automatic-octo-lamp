from django import template
from django.utils.translation import gettext
register=template.Library()
@register.filter
def ui(value):
    return gettext(str(value)) if value is not None else ''
