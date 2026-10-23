import json
from unittest.mock import patch,MagicMock
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from .local_ai import facts_only,generate,LOCAL_URL,MODEL
from .owner_dashboard import station_summary
from .models import AuditEvent

@override_settings(LOCAL_AI_URL=LOCAL_URL,LOCAL_AI_MODEL=MODEL)
class LocalAITests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner=get_user_model().objects.create_superuser('owner','','test-only')
        self.staff=get_user_model().objects.create_user('manager',is_staff=True)
        self.day=timezone.localdate()
    def payload(self,**kw):
        result={'date':str(self.day),'scope':'current','language':'English'};result.update(kw);return result
    def test_permissions_method_and_date(self):
        self.assertEqual(self.client.get('/ai-briefing/').status_code,302)
        self.client.force_login(self.staff);self.assertEqual(self.client.get('/ai-briefing/').status_code,403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get('/ai-briefing/').status_code,200)
        self.assertEqual(self.client.delete('/ai-briefing/').status_code,405)
        with patch('pump.local_ai.generate') as gen:
            self.assertEqual(self.client.post('/ai-briefing/',self.payload(date='bad')).status_code,400)
            self.assertEqual(self.client.post('/ai-briefing/',self.payload(scope='remote')).status_code,400)
            self.assertFalse(gen.called)
    def test_summary_allowlist_excludes_names_and_free_text(self):
        summary=station_summary(self.day);summary.update(name='SECRET name',customer='PRIVATE customer',notes='PRIVATE note',password='PRIVATE password')
        summary['stocks']=[{'name':'PRIVATE tank','fuel':'PETROL','litres':'100','warning':False}]
        raw=json.dumps(facts_only(summary))
        self.assertNotIn('PRIVATE',raw);self.assertNotIn('SECRET',raw)
        self.assertIn('PETROL',raw)
    @patch('pump.local_ai.build_opener')
    def test_local_url_no_tools_and_bounded_plain_response(self,opener):
        response=MagicMock();response.__enter__.return_value=response
        response.read.return_value=json.dumps({'done':True,'message':{'content':'{"priority_ids":["station1_day"]}'},'done_reason':'stop'}).encode()
        opener.return_value.open.return_value=response
        result=generate([facts_only(station_summary(self.day))],'Hindi')
        self.assertIn('अधूरा',result['text'])
        self.assertNotIn('All stations closed',result['text'])
        call=opener.return_value.open.call_args
        self.assertEqual(call.args[0].full_url,LOCAL_URL);self.assertEqual(call.kwargs['timeout'],50)
        data=json.loads(call.args[0].data)
        self.assertNotIn('tools',data);self.assertFalse(data['stream']);self.assertFalse(data['think'])
        self.assertEqual(data['model'],MODEL);self.assertEqual(data['keep_alive'],0)
        response.read.return_value=b'{"done":false}'
        with self.assertRaises(ValueError):generate([],'English')
        with override_settings(LOCAL_AI_URL='https://external.example/api/chat'):
            with self.assertRaises(ValueError):generate([],'English')
    @patch('pump.local_ai.generate')
    def test_post_renders_escaped_answer_and_no_ledger_write(self,gen):
        gen.return_value={'text':'<script>danger()</script>','truncated':False,'model':MODEL,'generated_at':timezone.now()}
        self.client.force_login(self.owner);before=AuditEvent.objects.count()
        response=self.client.post('/ai-briefing/',self.payload())
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'&lt;script&gt;danger()&lt;/script&gt;')
        self.assertEqual(AuditEvent.objects.count(),before)
        self.assertIn('no-store',response['Cache-Control'])
        self.assertFalse(cache.get('local-ai-briefing:station1'))
    @patch('pump.local_ai.generate')
    @patch('pump.local_ai.peer_summary',side_effect=ValueError('offline'))
    def test_no_briefing_with_missing_requested_station(self,peer,gen):
        self.client.force_login(self.owner)
        r=self.client.post('/ai-briefing/',self.payload(scope='both'))
        self.assertEqual(r.status_code,503);self.assertFalse(gen.called)
        self.assertContains(r,'No cloud service was used',status_code=503)
    @patch('pump.local_ai.generate',side_effect=TimeoutError())
    def test_timeout_and_duplicate_running_guard(self,gen):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post('/ai-briefing/',self.payload()).status_code,503)
        self.assertFalse(cache.get('local-ai-briefing:station1'))
        cache.add('local-ai-briefing:station1',True,65)
        self.assertEqual(self.client.post('/ai-briefing/',self.payload()).status_code,429)

    @patch('pump.local_ai.build_opener')
    def test_invented_or_duplicate_priority_is_rejected(self,opener):
        response=MagicMock();response.__enter__.return_value=response;opener.return_value.open.return_value=response
        for selected in [['invented_missing_balance'],['station1_day','station1_day'],[],['station1_day',42]]:
            response.read.return_value=json.dumps({'done':True,'message':{'content':json.dumps({'priority_ids':selected})}}).encode()
            with self.assertRaises(ValueError):generate([facts_only(station_summary(self.day))],'English')

    def test_complete_day_has_no_invented_missing_data_checks(self):
        from .local_ai import verified_checks
        f=facts_only(station_summary(self.day))
        f.update(complete_day=True,shifts=2,readings=16,cash_opening_available=True,bank_opening_available=True)
        status,checks=verified_checks([f],'English')
        self.assertIn('complete day',status[0])
        self.assertFalse(any(c['id'].endswith(('_day','_opening')) for c in checks))
