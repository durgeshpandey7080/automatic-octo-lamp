from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from pump.organisations import PortalLoginView, organisations, select_organisation, consume_ticket, portal_logout, consume_logout
urlpatterns = [path('sso/logout/', consume_logout, name='consume_logout'), path('organisations/', organisations, name='organisations'), path('organisations/select/', select_organisation, name='select_organisation'), path('sso/consume/', consume_ticket, name='consume_ticket'), path('admin/', admin.site.urls),
    path('login/', PortalLoginView.as_view(), name='login'),
    path('logout/', portal_logout, name='logout'),
    path('', include('pump.urls'))]
