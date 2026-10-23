"""Encrypted two-station SQLite recovery bundles. Never serves decrypted downloads."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import time
import uuid
import zipfile
from datetime import datetime, timezone, timedelta
from cryptography.fernet import Fernet

STATIONS = ('station1', 'station2')


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    os.replace(temp, path)


def check_database(path):
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('Database integrity check failed')
        if db.execute('PRAGMA foreign_key_check').fetchone():
            raise ValueError('Database foreign-key check failed')
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'django_migrations', 'auth_user', 'pump_shift'} <= tables:
            raise ValueError('Not a pump software database')
        # Counts give a useful restore-test comparison without exporting personal data.
        return {t: db.execute('SELECT COUNT(*) FROM "' + t + '"').fetchone()[0]
                for t in sorted(tables) if t.startswith('pump_') or t == 'auth_user'}


def unpack_verified(bundle, key, destination):
    """Stage only into an empty new directory; no writes to live databases."""
    if destination.exists():
        raise ValueError('Restore destination must not exist')
    raw = Fernet(key).decrypt(bundle.read_bytes())
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate archive paths')
        for name in names:
            parts = Path(name).parts
            if name.startswith(('/', '\\')) or '\\' in name or ':' in name or '..' in parts:
                raise ValueError('Unsafe archive path')
        manifest = json.loads(archive.read('manifest.json'))
        if manifest['format'] != 1 or set(manifest['stations']) != set(STATIONS):
            raise ValueError('Unsupported recovery bundle')
        if set(names) != set(manifest['files']) | {'manifest.json'}:
            raise ValueError('Unexpected or missing archive files')
        for name, digest in manifest['files'].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError('Recovery checksum failed')
        destination.mkdir(parents=True)
        try:
            for name in manifest['files']:
                target = destination / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))
            for station in STATIONS:
                counts = check_database(destination / 'databases' / (station + '.sqlite3'))
                if counts != manifest['stations'][station]['counts']:
                    raise ValueError('Restored record counts do not match')
            (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        except Exception:
            shutil.rmtree(destination)
            raise
    return manifest


def create_bundle(data_root, project, output, key):
    output.mkdir(parents=True, exist_ok=True)
    started = now()
    manifest = {'format': 1, 'started_at': started, 'stations': {}, 'files': {}}
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        payload = {}
        for station in STATIONS:
            source = data_root / station / 'db.sqlite3'
            if not source.is_file():
                raise ValueError('Missing database for ' + station)
            snapshot = stage / (station + '.sqlite3')
            with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=30) as src:
                with sqlite3.connect(snapshot) as dst:
                    deadline = time.monotonic() + 120
                    def progress(*args):
                        if time.monotonic() > deadline:
                            raise TimeoutError('SQLite backup timed out')
                    src.backup(dst, pages=256, progress=progress, sleep=.1)
            manifest['stations'][station] = {'snapshot_at': now(), 'counts': check_database(snapshot)}
            payload['databases/' + station + '.sqlite3'] = snapshot.read_bytes()
            # Future uploaded documents must live in this persistent media folder.
            media = data_root / station / 'media'
            if media.exists():
                for file in media.rglob('*'):
                    if file.is_symlink():
                        raise ValueError('Symlinks are not supported in uploads')
                    if file.is_file():
                        payload['media/' + station + '/' + file.relative_to(media).as_posix()] = file.read_bytes()
        for file in project.rglob('*'):
            rel = file.relative_to(project)
            if any(p in {'.git', '.venv', '__pycache__', 'backups', 'node_modules'} for p in rel.parts):
                continue
            if file.is_symlink():
                raise ValueError('Symlinks are not supported in recovery sources')
            if file.is_file() and file.suffix not in {'.sqlite3', '.pyc', '.zip'} and 'LOGIN' not in file.name.upper():
                payload['project/' + rel.as_posix()] = file.read_bytes()
        if 'project/.env' not in payload:
            raise ValueError('Private installation settings are missing')
        manifest['files'] = {n: hashlib.sha256(b).hexdigest() for n, b in payload.items()}
        memory = io.BytesIO()
        with zipfile.ZipFile(memory, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, data in payload.items():
                archive.writestr(name, data)
            archive.writestr('manifest.json', json.dumps(manifest))
        token = Fernet(key).encrypt(memory.getvalue())
        name = 'pump-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8] + '.pumpbackup'
        partial = output / (name + '.partial')
        partial.write_bytes(token)
        try:
            unpack_verified(partial, key, stage / 'restore-test')
            os.replace(partial, output / name)
        finally:
            partial.unlink(missing_ok=True)
    return {'filename': name, 'completed_at': now(), 'bytes': len(token),
            'sha256': hashlib.sha256(token).hexdigest(), 'restore_tested_at': now(),
            'station_snapshots': {s: manifest['stations'][s]['snapshot_at'] for s in STATIONS}}


def run_once():
    output = Path(os.environ.get('BACKUP_DIR', '/backups'))
    output.mkdir(parents=True, exist_ok=True)
    status_path = output / 'status.json'
    try:
        status = json.loads(status_path.read_text())
    except (OSError, ValueError):
        status = {}
    status.update(last_attempt_at=now(), running=True)
    atomic_json(status_path, status)
    try:
        key = Path(os.environ.get('BACKUP_KEY_FILE', '/recovery/backup.key')).read_bytes().strip()
        result = create_bundle(Path(os.environ.get('BACKUP_SOURCES_DIR', '/sources')),
                               Path(os.environ.get('BACKUP_PROJECT_DIR', '/project')), output, key)
        status.update(last_success=result, last_error=None)
        secondary = Path(os.environ.get('BACKUP_SECONDARY_DIR', '/secondary'))
        try:
            secondary.mkdir(parents=True, exist_ok=True)
            target = secondary / result['filename']
            partial = target.with_suffix('.partial')
            shutil.copyfile(output / result['filename'], partial)
            if hashlib.sha256(partial.read_bytes()).hexdigest() != result['sha256']:
                raise ValueError('Secondary copy checksum mismatch')
            os.replace(partial, target)
            status.update(last_secondary={'filename': result['filename'], 'copied_at': now()}, secondary_error=None)
        except Exception as error:
            status['secondary_error'] = type(error).__name__ + ': second copy failed; primary backup retained.'
        # Keep at least the newest 48 archives, and every archive from the last 30 days.
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        bundles = sorted(output.glob('pump-*.pumpbackup'), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in bundles[48:]:
            if datetime.fromtimestamp(old.stat().st_mtime, timezone.utc) < cutoff:
                old.unlink()
        # Apply the same policy independently to successfully copied secondary bundles.
        if not status.get('secondary_error'):
            copies = sorted(secondary.glob('pump-*.pumpbackup'), key=lambda p: p.stat().st_mtime, reverse=True)
            for old in copies[48:]:
                if datetime.fromtimestamp(old.stat().st_mtime, timezone.utc) < cutoff:
                    old.unlink()
    except Exception as error:
        # Exception text may contain private filenames or environment data; log type only.
        status['last_error'] = type(error).__name__ + ': backup failed; inspect storage, key and database availability.'
    finally:
        status.update(running=False, last_attempt_finished_at=now())
        atomic_json(status_path, status)
    return not status.get('last_error')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['daemon', 'once', 'verify', 'restore-stage'])
    parser.add_argument('--bundle')
    parser.add_argument('--destination')
    args = parser.parse_args()
    if args.command in {'verify', 'restore-stage'}:
        key = Path(os.environ.get('BACKUP_KEY_FILE', '/recovery/backup.key')).read_bytes().strip()
        if args.command == 'verify':
            with tempfile.TemporaryDirectory() as tmp:
                unpack_verified(Path(args.bundle), key, Path(tmp) / 'restored')
        else:
            unpack_verified(Path(args.bundle), key, Path(args.destination))
        print('Both databases, record counts and recovery files verified.')
    elif args.command == 'once':
        raise SystemExit(0 if run_once() else 1)
    else:
        while True:
            succeeded = run_once()
            # A file request avoids exposing Docker or encryption keys to the website.
            for _ in range(360 if succeeded else 6):
                time.sleep(10)
                request = Path('/requests/run')
                if request.exists():
                    request.unlink(missing_ok=True)
                    break


if __name__ == '__main__':
    main()
