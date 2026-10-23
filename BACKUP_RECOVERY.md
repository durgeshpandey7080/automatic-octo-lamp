# Backups and recovery

This is a local development system. A passing restore rehearsal verifies recoverable files and database integrity, not production readiness or the correctness of every business entry.

## What is running

The Docker `backup` service makes a bundle immediately on startup, then approximately hourly. It handles owner requests from **Backups & recovery** within about 10 seconds when idle. Docker Desktop and the computer must be running. Missed hours are not recreated; the next startup takes a fresh backup. All services use `unless-stopped` restart policies, but Windows/Docker startup still depends on the PC's Docker Desktop settings.

Each bundle contains:

- Separate consistent SQLite online-backup snapshots for Hamara Pump Narai and Shree Govind KSK, with integrity checks, foreign-key checks and table counts.
- Matching project source, templates, static files, dependencies, Compose configuration and private `.env` installation settings. Login instruction files, loose database files and caches are excluded.
- Uploads under `/data/media/` in each station volume. Current business records live in the databases; arbitrary Desktop files and chat attachments are not application uploads and are not included.
- An internal manifest with timestamps, file SHA-256 digests and database record counts.

The whole bundle is authenticated and encrypted using Fernet. Every successful bundle is decrypted into temporary storage, restored, checksum-checked and checked against the saved record counts before publication. This uses memory for the compressed bundle; large future uploads require a streaming backup design. The service has read-only mounts of the live databases and project, no Docker socket and no web port.

The databases are snapshotted one after another, not in one global transaction. Source and media copies are not atomic: avoid source upgrades or changing attachments during backup. Prefer a quiet period for a manual pre-upgrade snapshot.

## Actual folders on this installation

All are siblings of `hpcl_pump` under `outputs`:

- `pump-backups`: primary `.pumpbackup` files and `status.json`.
- `pump-backups-secondary`: checksum-verified second copies.
- `pump-recovery/backup.key`: private decryption key. Never send this in chat or email, publish it, or add it to a source ZIP.

Windows ACLs restrict these folders to the installing Windows user, SYSTEM and Administrators. Local administrators and Docker administrators can still access them. The service requires the key to run; keep a separate protected copy of the key for PC-loss recovery. The key is deliberately outside the source project and outside recovery bundles. Losing every copy of the key makes encrypted backups unusable.

**The two backup folders are on the same PC/disk. They do not protect against disk failure, theft or ransomware affecting both.** Copy encrypted bundles to a disconnected external drive and keep the key separately in a protected location. An external location has not been configured. Never mistake a source-code ZIP for a business-data backup.

Retention: keep at least the newest 48 bundles and all bundles from the previous 30 days, independently in each folder. Pruning runs only after a successful new primary backup (and successful secondary copy for secondary pruning). A secondary failure retains the primary and shows a separate error. A failed primary attempt retains the last success timestamp and shows an error. A primary backup older than two hours triggers a warning in the owner page. Repeated manual backups increase storage usage; monitor free space.

## Setup / manual request

From Windows PowerShell in the project directory:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup-local.ps1
```

Existing installation keys are retained. For an existing configured installation, `setup-backups.ps1` is also safe to rerun. No data volumes are removed. In the software, sign in as superadmin, select **Backups & recovery**, then **Back up now**. Refresh after completion. Ordinary staff cannot view this page or request backups. Backup keys and decrypted archives are not served by the website.

## Rehearse recovery without replacing live data

Choose an actual filename from the owner screen or the primary backup folder:

```powershell
.\restore-backup.ps1 -BackupFile 'pump-YYYYMMDDTHHMMSSZ-xxxxxxxx.pumpbackup'
```

Replace the example filename. This decrypts and restores both databases to temporary storage in a one-off container, checks integrity/counts, then removes the temporary files. A wrong key, tampered file, unsafe archive path or corrupt database fails the check. Live records are unchanged.

## Apply recovery on this PC (deliberate maintenance operation)

1. Have all staff stop entry. Identify the exact backup time; later entries will be replaced.
2. Rehearse with the command above first. Preserve a copy of the bundle and key.
3. Run:

```powershell
.\restore-backup.ps1 -BackupFile 'pump-YYYYMMDDTHHMMSSZ-xxxxxxxx.pumpbackup' -Apply -ConfirmRestore 'RESTORE BOTH ORGANISATIONS'
```

The script stops both apps and the scheduled backup service, stages/verifies the selected archive, makes a new verified safety backup of the current data, then replaces both databases and restores uploads. It checks both database migration versions before any replacement. It refuses mismatched versions rather than using old data with newer code. Old uploads are preserved as `media.before-restore`; inspect that folder before another restore. Completed staging files are removed. Settings/source are retained on this same-PC operation.

There is no global filesystem transaction across the two volumes. On any apply failure the script stops, leaving apps stopped; do not restart entry until both databases are checked. Use the newly created safety bundle to recover both together. Failed staging may contain decrypted data in the protected primary folder; inspect and remove that specific staging folder after recovery. Never delete entire data volumes. Successful apply starts services again; compare balances, daily totals and recent records in both organisations before staff resume.

This script is designed for this Compose project name (`hpcl_pump`) and volume names. Do not run it against a different installation without adapting and reviewing those targets. It is intentionally unavailable as a web button.

## Complete recovery after PC loss or incompatible schema

Use a separate recovery installation first; keep the old installation untouched where available.

1. Install Docker Desktop and obtain the recovery tooling/project ZIP.
2. Restore the private backup key to the protected `pump-recovery/backup.key` folder, and the encrypted bundle to `pump-backups`. Do not let setup replace an existing recovery key.
3. Run `restore-stage` in a one-off backup container into a new protected folder, e.g. `/backups/recovery-stage-<unique-id>`; it validates all contents before use.
4. Recover the archived `project/` contents (including `.env`) to a separate project directory. Review path/network settings on the replacement PC. Use the archived requirements and migrations; build the matching image.
5. With apps stopped, populate the two data volumes from the staged `databases/` and `media/` files, maintaining UID/GID 10001. The same-PC apply script intentionally refuses empty/mismatched databases; complete disaster recovery requires this operator-assisted volume provisioning.
6. Verify both databases, start the matching app version, sign in, compare records and rehearse a new backup. Reapply approved upgrades only after the restored installation is verified.

Do not restore old settings or source over an active newer installation without checking compatibility. The automated rehearsal tests database/file recovery; a complete replacement-PC rebuild and real live rollback have not been performed on this user's PC.

Implementation references: Python SQLite online backup API https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup and Fernet authenticated encryption https://cryptography.io/en/latest/fernet/ .
