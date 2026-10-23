from django.http import HttpResponseForbidden
from .models import StaffAccess


def role_for(user):
    if user.is_superuser:
        return 'OWNER'
    access = StaffAccess.objects.filter(user=user).first()
    if access:
        return access.role if access.active else 'DISABLED'
    # Preserve existing accounts while the owner assigns explicit station roles.
    return 'LEGACY_MANAGER' if user.is_staff else 'LEGACY_CASHIER'


def can_manage(user):
    return role_for(user) in {'OWNER', 'MANAGER', 'LEGACY_MANAGER'}


class StationRoleMiddleware:
    """Enforce explicitly assigned roles at app and admin endpoints, not just menu links."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_superuser:
            role = role_for(request.user)
            route = request.path_info
            if route in {'/logout/', '/sso/logout/', '/language/'}:
                return self.get_response(request)
            forbidden = role == 'DISABLED'
            if role in {'CASHIER', 'VIEWER', 'ACCOUNTANT'}:
                forbidden |= route.startswith(('/admin/', '/staff-access/', '/backups/'))
            if role == 'MANAGER':
                forbidden |= route.startswith(('/admin/', '/staff-access/', '/backups/'))
            if role == 'CASHIER':
                forbidden |= route.startswith(('/salaries/', '/suppliers/', '/money-book/', '/payment-imports/'))
                if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
                    # Resolution occurs after __call__; resolve here using path_info.
                    from django.urls import resolve, Resolver404
                    try:
                        name = resolve(route).url_name
                    except Resolver404:
                        return self.get_response(request)
                    forbidden |= name not in {'entry', 'handover_detail', 'duty_add', 'credit_sale_add', 'lube_sale_add', 'day_close'}
            if role in {'VIEWER', 'ACCOUNTANT'} and request.method not in {'GET', 'HEAD', 'OPTIONS'}:
                forbidden = True
            if forbidden:
                return HttpResponseForbidden('Your assigned station role does not allow this action. Contact the owner.')
        return self.get_response(request)
