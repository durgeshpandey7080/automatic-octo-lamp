from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import PaymentEvidence, PaymentImportBatch, DigitalCollection, Shift, Salesperson
from .payment_imports import preview_csv, commit_import, match_evidence
from django.core.files.uploadedfile import SimpleUploadedFile


class PaymentImportTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser('import-owner', '', 'test-pass')
        self.date = timezone.localdate()
        self.header = 'reference,date,amount,status,description\n'

    def preview(self, reference='TX-1', amount='100.00', extra=''):
        return preview_csv((self.header + f'{reference},{self.date},{amount},SUCCESS,Fuel\n' + extra).encode())

    def test_duplicate_files_and_overlapping_exports_do_not_duplicate_transactions(self):
        preview = self.preview()
        batch, created = commit_import(preview,'PAYTM','MERCHANT-1',self.owner)
        self.assertTrue(created)
        self.assertFalse(commit_import(preview,'PAYTM','MERCHANT-1',self.owner)[1])
        overlap = self.preview(extra=f'TX-2,{self.date},50.00,SUCCESS,Fuel\n')
        second, _ = commit_import(overlap,'PAYTM','MERCHANT-1',self.owner)
        self.assertEqual((second.new_rows,second.duplicate_rows),(1,1))
        self.assertEqual(PaymentEvidence.objects.count(),2)
        with self.assertRaises(ValidationError):
            commit_import(self.preview(amount='101.00'),'PAYTM','MERCHANT-1',self.owner)
        self.assertEqual(PaymentImportBatch.objects.count(),2)
        self.assertEqual(DigitalCollection.objects.count(),0)

    def test_bad_amounts_duplicate_references_and_failed_rows_are_rejected(self):
        for amount in ['NaN','Infinity','0','-1','1.001','10000000000']:
            with self.assertRaises(ValidationError):
                self.preview(amount=amount)
        with self.assertRaises(ValidationError):
            self.preview(extra=f'TX-1,{self.date},100.00,SUCCESS,Duplicate\n')
        with self.assertRaises(ValidationError):
            preview_csv((self.header+f'TX-1,{self.date},100.00,PENDING,Fuel\n').encode())

    def test_match_requires_exact_existing_collection_and_does_not_create_settlement(self):
        batch,_=commit_import(self.preview(),'PAYTM','MERCHANT-1',self.owner)
        evidence=PaymentEvidence.objects.get(batch=batch)
        shift=Shift.objects.create(date=self.date,number=1)
        person=Salesperson.objects.create(name='Import salesperson')
        collection=DigitalCollection.objects.create(shift=shift,salesperson=person,method='PAYTM',amount='99.00',reference='TX-1',terminal='MERCHANT-1',recorded_by=self.owner)
        with self.assertRaises(ValidationError):
            match_evidence(evidence.pk,collection.pk,self.owner)

        collection.amount='100.00';collection.save()
        self.assertEqual(match_evidence(evidence.pk,collection.pk,self.owner).collection_id,collection.pk)
        self.assertEqual(collection.reconciliations.count(),0)
        with self.assertRaises(ValidationError):
            match_evidence(evidence.pk,collection.pk,self.owner)

    def test_upload_preview_confirmation_and_invalid_replacement_preview(self):
        self.client.force_login(self.owner)
        raw=(self.header+f'TX-UI,{self.date},100.00,SUCCESS,Fuel\n').encode()
        response=self.client.post('/payment-imports/',{'action':'preview','provider':'PAYTM','merchant':'MERCHANT-UI','file':SimpleUploadedFile('report.csv',raw)})
        self.assertContains(response,'Confirm 1 rows')
        self.assertEqual(PaymentEvidence.objects.count(),0)
        self.assertEqual(self.client.post('/payment-imports/',{'action':'commit'}).status_code,302)
        self.assertEqual(PaymentEvidence.objects.count(),1)
        self.client.post('/payment-imports/',{'action':'preview','provider':'PAYTM','merchant':'MERCHANT-UI','file':SimpleUploadedFile('report.csv',raw)})
        self.client.post('/payment-imports/',{'action':'preview','provider':'PAYTM','merchant':'MERCHANT-UI','file':SimpleUploadedFile('bad.csv',b'wrong headings')})
        self.assertNotIn('payment_import_preview',self.client.session)
