import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings


@login_required
def backups(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden('Only the owner superadmin can manage backups.')
    root = Path(getattr(settings, 'BACKUP_STATUS_DIR', '/backups'))
    try:
        status = json.loads((root / 'status.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        status = {}
    success = status.get('last_success', {})
    fresh = False
    if success:
        try:
            fresh = datetime.now(timezone.utc) - datetime.fromisoformat(success['completed_at']) < timedelta(hours=2)
            filename = success['filename']
            fresh = fresh and Path(filename).name == filename and (root / filename).is_file()
        except (KeyError, ValueError, TypeError):
            pass
    if request.method == 'POST':
        try:
            request_dir = Path(getattr(settings, 'BACKUP_REQUEST_DIR', '/backup-requests'))
            request_dir.mkdir(parents=True, exist_ok=True)
            (request_dir / 'run').touch()
            messages.success(request, 'Backup requested. The backup service normally picks this up within 10 seconds. Refresh to check completion.')
        except OSError:
            messages.error(request, 'Cannot request a backup. Check the backup service and request folder.')
        return redirect('backups')
    bundles = sorted(root.glob('pump-*.pumpbackup'), reverse=True)[:20] if root.exists() else []
    return render(request, 'pump/backups.html', {'page_name': 'Backups & recovery',
        'backup_status': status, 'success': success, 'fresh': fresh,
        'bundles': [{'name': p.name, 'bytes': p.stat().st_size} for p in bundles]})
