# Repository import - 23 October 2026

This repository contains the current local pump application source, migrations through 0032, templates, static assets, tests, Docker configuration, setup/recovery scripts and operational documentation. It was copied from `outputs/hpcl_pump` into a separate checkout so the running installation and business databases were not changed.

`docs/project-report-site` preserves the separate progress website source. Its progress/test counts are an older snapshot, not the current verification result. Hosting metadata and credentials were excluded; importing this source does not deploy the website.

Private environment files, databases, database backups, recovery keys, login files, temporary work and ZIP archives are excluded. Restore business data using the documented private backup process; GitHub is a source-code repository, not a business-data backup.

## Work on this checkout safely

The original Windows setup/recovery scripts target the existing `hpcl_pump` Compose project, its external backup-request volume, and backup folders next to the source folder. The Compose configuration also contains the original LAN address. Do not run the setup scripts from this checkout just to test the code: they can address the existing running installation. Configure a separate Compose project, volumes, backup paths, LAN links and host port before starting a second installation.

For source verification, use the isolated containers below. They mount no station volumes, require no private `.env`, and use a temporary database inside the disposable container:

```powershell
docker build -t pump-repo-verification:latest .
docker run --rm -e PUMP_DB_PATH=/tmp/pump-verification.sqlite3 pump-repo-verification:latest python manage.py check
docker run --rm -e PUMP_DB_PATH=/tmp/pump-verification.sqlite3 pump-repo-verification:latest python manage.py makemigrations --check --dry-run
docker run --rm -e PUMP_DB_PATH=/tmp/pump-verification.sqlite3 pump-repo-verification:latest python manage.py test --noinput
```

See `DESIGN_BRIEF.md` for the owner's confirmed redesign priorities. This import preserves the existing interface; the owner dashboard redesign remains to be specified.

## Verified for this import

- Docker image built successfully from the copied application source.
- Django system check passed with no issues.
- Migration consistency check passed: no changes detected.
- All 146 automated tests passed in 22.554 seconds using a disposable test database.
- Progress website build and JavaScript syntax check passed.

These checks do not establish production readiness or verify the eventual phone redesign. GitHub Actions runs the Django checks again on pushes and pull requests; the local results above are separate from hosted CI status.
