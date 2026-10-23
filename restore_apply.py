"""Invoked by restore-backup.ps1 ONLY after services are stopped and backup verified."""
import os
from pathlib import Path
import shutil
import sqlite3
import sys
from backup_runner import check_database


def preserve_owner(path, owner):
    """Match the existing installation, rather than assuming a container UID."""
    if hasattr(os, 'chown'):
        current = path.stat()
        if (current.st_uid, current.st_gid) != owner:
            # Failure must stop recovery; do not silently leave app data inaccessible.
            os.chown(path, *owner)


def apply(stage, target_root):
    # Fail before replacing anything if backup schema differs from installed databases.
    def migrations(path):
        with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
            return set(db.execute('SELECT app, name FROM django_migrations'))
    owners = {}
    for station in ('station1', 'station2'):
        saved = stage / 'databases' / (station + '.sqlite3')
        live = target_root / station / 'db.sqlite3'
        check_database(saved)
        check_database(live)
        live_stat = live.stat()
        owners[station] = (live_stat.st_uid, live_stat.st_gid)
        if migrations(saved) != migrations(live):
            raise ValueError('Schema versions differ. Restore matching project source in an isolated recovery installation first.')
        if (target_root / station / 'media').exists() and (target_root / station / 'media.before-restore').exists():
            raise ValueError('Previous recovery upload folder exists; inspect it before another restore.')
    for station in ('station1', 'station2'):
        target = target_root / station
        # Stopped app: stale SQLite journal files must not be replayed over restored data.
        for suffix in ('-wal', '-shm', '-journal'):
            (target / ('db.sqlite3' + suffix)).unlink(missing_ok=True)
        shutil.copyfile(stage / 'databases' / (station + '.sqlite3'), target / 'db.sqlite3.restoring')
        shutil.copymode(target / 'db.sqlite3', target / 'db.sqlite3.restoring')
        preserve_owner(target / 'db.sqlite3.restoring', owners[station])
        os.replace(target / 'db.sqlite3.restoring', target / 'db.sqlite3')
        media = target / 'media'
        previous = target / 'media.before-restore'
        # Preserve previous uploads if present; never recursively erase operational uploads.
        if media.exists():
            if previous.exists():
                raise ValueError('Previous recovery upload folder exists; inspect it before another restore.')
            media.rename(previous)
        saved_media = stage / 'media' / station
        if saved_media.exists():
            shutil.copytree(saved_media, media)
            for item in [media, *media.rglob('*')]:
                preserve_owner(item, owners[station])
        check_database(target / 'db.sqlite3')
    print('Both databases restored. Recheck daily totals before allowing entries.')
    if stage.parent == Path('/backups') and stage.name.startswith('recovery-stage-'):
        shutil.rmtree(stage)


if __name__ == '__main__':
    apply(Path(sys.argv[1]), Path('/restore'))
