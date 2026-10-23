from django.test import TestCase, override_settings, RequestFactory
from django.contrib.auth import get_user_model
from .context_processors import station

class StationConfigurationTests(TestCase):
    @override_settings(STATION_NAME='Second Pump', STATION_CODE='station2', STATION_LINKS=[])
    def test_station_brand_on_login(self):
        user = get_user_model().objects.create_user('branding-test')
        self.client.force_login(user)
        response = self.client.get('/')
        self.assertContains(response, 'Second Pump')
        self.assertContains(response, 'Pandey Petrol Pump')

    @override_settings(STATION_NAME='Second Pump', STATION_CODE='station2',
        STATION_LINKS=[{'code':'station1','name':'First Pump','url':'http://127.0.0.1:8000/'}])
    def test_selector_and_current_station(self):
        user = get_user_model().objects.create_user('station-test')
        self.client.force_login(user)
        response = self.client.get('/')
        self.assertContains(response, 'Switch organisation')
        self.assertContains(response, 'Second Pump')
        self.assertContains(response, 'http://127.0.0.1:8000/')
        self.assertEqual(station(RequestFactory().get('/'))['station_code'], 'station2')


class OrganisationLoginTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser('owner', password='test-password-only')

    def test_owner_login_goes_to_owner_dashboard(self):
        response = self.client.post('/login/?next=/', {'username':'owner', 'password':'test-password-only'})
        self.assertRedirects(response, '/owner/', fetch_redirect_response=False)

    def test_manager_login_keeps_organisation_chooser(self):
        get_user_model().objects.create_user('station-manager', password='test-password-only', is_staff=True)
        response=self.client.post('/login/', {'username':'station-manager', 'password':'test-password-only'})
        self.assertRedirects(response, '/organisations/')

    @override_settings(STATION_LINKS=[{'code':'station1','name':'Hamara Pump Narai','url':'http://127.0.0.1:8000/'},
        {'code':'station2','name':'Shree Govind KSK','url':'http://127.0.0.1:8000/station2/'}])
    def test_select_and_ticket(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get('/organisations/'), 'Shree Govind KSK')
        self.assertRedirects(self.client.post('/organisations/select/', {'organisation':'station1'}), '/')
        response = self.client.post('/organisations/select/', {'organisation':'station2'})
        self.assertContains(response, '/station2/sso/consume/')
        ticket = response.context['ticket']
        self.client.logout()
        with self.settings(STATION_CODE='station2'):
            response = self.client.post('/sso/consume/', {'ticket':ticket})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(str(self.user.pk), self.client.session['_auth_user_id'])
            self.assertEqual(self.client.post('/sso/consume/', {'ticket':ticket}).status_code, 403)

    @override_settings(STATION_CODE='station2')
    def test_second_station_redirects_to_single_login(self):
        response = self.client.get('/login/')
        self.assertEqual(response.url, 'http://127.0.0.1:8000/login/')
        self.assertEqual(self.client.post('/sso/consume/', {'ticket':'invalid'}).status_code, 403)


    def test_logout_closes_both_organisation_sessions(self):
        self.client.force_login(self.user)
        response = self.client.post('/logout/')
        ticket = response.context['ticket']
        self.assertNotIn('_auth_user_id', self.client.session)
        with self.settings(STATION_CODE='station2'):
            self.client.force_login(self.user)
            response = self.client.post('/sso/logout/', {'ticket':ticket})
            self.assertEqual(response.status_code, 302)
            self.assertNotIn('_auth_user_id', self.client.session)


class TopbarOrganisationSwitchTests(TestCase):
    @override_settings(STATION_CODE='station2', STATION_LINKS=[{'code':'station1','name':'Hamara Pump Narai','url':'http://127.0.0.1:8000/'},{'code':'station2','name':'Shree Govind KSK','url':'http://127.0.0.1:8000/station2/'}])
    def test_secondary_can_switch_directly_to_primary(self):
        user=get_user_model().objects.create_superuser('topbar-owner',password='test-only')
        self.client.force_login(user)
        response=self.client.post('/organisations/select/',{'organisation':'station1'})
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'http://127.0.0.1:8000/sso/consume/')
        ticket=response.context['ticket']
        with self.settings(STATION_CODE='station1'):
            self.client.logout()
            response=self.client.post('/sso/consume/',{'ticket':ticket})
            self.assertEqual(response.status_code,302)
            self.assertEqual(self.client.session['_auth_user_id'],str(user.pk))
    @override_settings(STATION_LINKS=[{'code':'station1','name':'Hamara Pump Narai','url':'http://127.0.0.1:8000/'},{'code':'station2','name':'Shree Govind KSK','url':'http://127.0.0.1:8000/station2/'}])
    def test_switcher_present_and_staff_cannot_escalate(self):
        user=get_user_model().objects.create_user('local-staff',is_staff=True)
        self.client.force_login(user)
        self.assertContains(self.client.get('/stock/'),'aria-label="Switch organisation"')
        self.assertContains(self.client.get('/admin/'),'aria-label="Switch organisation"')
        self.assertEqual(self.client.post('/organisations/select/',{'organisation':'station2'}).status_code,403)
