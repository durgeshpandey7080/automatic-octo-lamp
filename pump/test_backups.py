from pathlib import Path
import io
import json
import sqlite3
import tempfile
import os
from unittest.mock import patch
import zipfile
from unittest import TestCase as UnitTestCase
from cryptography.fernet import Fernet, InvalidToken
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from backup_runner import create_bundle, unpack_verified, run_once
from restore_apply import apply


class RecoveryBundleTests(UnitTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.key = Fernet.generate_key()
        self.project = self.root / 'project'
        self.project.mkdir()
        (self.project / '.env').write_text('PUMP_SECRET_KEY=test-only')
        (self.project / 'README.md').write_text('recovery source')
        for station in ('station1', 'station2'):
            folder = self.root / 'sources' / station
            folder.mkdir(parents=True)
            with sqlite3.connect(folder / 'db.sqlite3') as db:
                db.executescript('CREATE TABLE django_migrations(app TEXT, name TEXT); CREATE TABLE auth_user(id INTEGER PRIMARY KEY); CREATE TABLE pump_shift(id INTEGER PRIMARY KEY);')
                db.execute('INSERT INTO pump_shift VALUES (?)', (1 if station == 'station1' else 2,))
            (folder / 'media').mkdir()
            (folder / 'media' / 'invoice.txt').write_text(station)

    def bundle(self):
        result = create_bundle(self.root / 'sources', self.project, self.root / 'bundles', self.key)
        return self.root / 'bundles' / result['filename']

    def test_restore_both_stations_settings_and_uploads_without_changing_live_data(self):
        bundle = self.bundle()
        with sqlite3.connect(self.root / 'sources/station1/db.sqlite3') as db:
            db.execute('INSERT INTO pump_shift VALUES (3)')
        dest = self.root / 'restored'
        unpack_verified(bundle, self.key, dest)
        with sqlite3.connect(dest / 'databases/station1.sqlite3') as db:
            self.assertEqual(db.execute('SELECT id FROM pump_shift').fetchall(), [(1,)])
        with sqlite3.connect(self.root / 'sources/station1/db.sqlite3') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM pump_shift').fetchone()[0], 2)
        self.assertEqual((dest / 'media/station2/invoice.txt').read_text(), 'station2')
        self.assertEqual((dest / 'project/.env').read_text(), 'PUMP_SECRET_KEY=test-only')
        with self.assertRaises(ValueError):
            unpack_verified(bundle, self.key, dest)

    def test_wrong_key_and_corrupted_bundle_rejected_before_writing(self):
        bundle = self.bundle()
        with self.assertRaises(InvalidToken):
            unpack_verified(bundle, Fernet.generate_key(), self.root / 'wrong')
        bundle.write_bytes(bundle.read_bytes()[:-12] + b'corrupted')
        with self.assertRaises(InvalidToken):
            unpack_verified(bundle, self.key, self.root / 'corrupt')
        self.assertFalse((self.root / 'corrupt').exists())

    def test_traversal_in_authenticated_archive_is_rejected(self):
        memory = io.BytesIO()
        with zipfile.ZipFile(memory, 'w') as archive:
            archive.writestr('../escape', 'bad')
        bundle = self.root / 'bad.pumpbackup'
        bundle.write_bytes(Fernet(self.key).encrypt(memory.getvalue()))
        with self.assertRaises(ValueError):
            unpack_verified(bundle, self.key, self.root / 'unsafe')
        self.assertFalse((self.root / 'escape').exists())

    def test_missing_station_does_not_publish_successful_bundle(self):
        (self.root / 'sources/station2/db.sqlite3').unlink()
        with self.assertRaises(ValueError):
            self.bundle()
        self.assertEqual(list((self.root / 'bundles').glob('*.pumpbackup')), [])

    def test_second_copy_failure_preserves_primary_and_later_retry_recovers(self):
        keyfile = self.root / 'key'
        keyfile.write_bytes(self.key)
        secondary = self.root / 'secondary'
        secondary.write_text('simulate unavailable folder')
        with patch.dict(os.environ, {'BACKUP_DIR': str(self.root / 'bundles'),
                'BACKUP_KEY_FILE': str(keyfile), 'BACKUP_PROJECT_DIR': str(self.project),
                'BACKUP_SOURCES_DIR': str(self.root / 'sources'), 'BACKUP_SECONDARY_DIR': str(secondary)}):
            self.assertTrue(run_once())
            status = json.loads((self.root / 'bundles/status.json').read_text())
            self.assertTrue(status['secondary_error'])
            self.assertTrue((self.root / 'bundles' / status['last_success']['filename']).exists())
            secondary.unlink()
            self.assertTrue(run_once())
            status = json.loads((self.root / 'bundles/status.json').read_text())
            self.assertIsNone(status['secondary_error'])
            self.assertEqual((secondary / status['last_success']['filename']).read_bytes(),
                             (self.root / 'bundles' / status['last_success']['filename']).read_bytes())
            (self.root / 'sources/station2/db.sqlite3').unlink()
            self.assertFalse(run_once())
            failed = json.loads((self.root / 'bundles/status.json').read_text())
            self.assertEqual(failed['last_success'], status['last_success'])
            self.assertTrue(failed['last_error'])

    def test_offline_apply_restores_both_stations_and_rejects_schema_mismatch(self):
        stage = self.root / 'restore-stage'
        unpack_verified(self.bundle(), self.key, stage)
        live = self.root / 'sources'
        with sqlite3.connect(live / 'station1/db.sqlite3') as db:
            db.execute('INSERT INTO pump_shift VALUES (99)')
        ownership={station:(live/station/'db.sqlite3').stat() for station in ('station1','station2')}
        apply(stage, live)
        for station, before_stat in ownership.items():
            restored=(live/station/'db.sqlite3').stat()
            self.assertEqual((restored.st_uid,restored.st_gid),(before_stat.st_uid,before_stat.st_gid))
        with sqlite3.connect(live / 'station1/db.sqlite3') as db:
            self.assertEqual(db.execute('SELECT id FROM pump_shift').fetchall(), [(1,)])
        self.assertEqual((live / 'station2/media/invoice.txt').read_text(), 'station2')
        # A changed migration prevents touching either database.
        with sqlite3.connect(live / 'station2/db.sqlite3') as db:
            db.execute("INSERT INTO django_migrations VALUES ('pump','new-schema')")
        before = (live / 'station1/db.sqlite3').read_bytes()
        with self.assertRaises(ValueError):
            apply(stage, live)
        self.assertEqual((live / 'station1/db.sqlite3').read_bytes(), before)


class BackupPageTests(TestCase):
    def test_owner_only_status_and_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(BACKUP_STATUS_DIR=tmp, BACKUP_REQUEST_DIR=tmp):
                self.assertEqual(self.client.get('/backups/').status_code, 302)
                staff = get_user_model().objects.create_user('cashier', is_staff=True)
                self.client.force_login(staff)
                self.assertEqual(self.client.get('/backups/').status_code, 403)
                self.assertEqual(self.client.post('/backups/').status_code, 403)
                staff.is_superuser = True
                staff.save()
                response = self.client.get('/backups/')
                self.assertContains(response, 'No recent successful backup')
                self.assertEqual(self.client.post('/backups/').status_code, 302)
                self.assertTrue((Path(tmp) / 'run').exists())
