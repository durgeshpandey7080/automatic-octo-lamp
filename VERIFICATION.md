# Verification

Verified with Django 5.2.18 in the authoring environment:

- All 14 tests passed, including authenticated entry, meter validation, continuity,
  atomic rollback, duplicate constraints, malformed form counts and CSRF protection.
- All migrations applied successfully to a new SQLite database.
- `makemigrations --check --dry-run`: no changes detected.
- Django system check: no issues.

After installing Docker Desktop and restarting Windows on 18 October 2026:

- Docker engine 29.8.2 and Compose v5.6.0 were verified.
- The Docker image built successfully with Python 3.13 and Django 5.2.18.
- All 14 tests also passed inside the Docker container.
- Migrations applied to the persistent Docker volume successfully.
- Demo tanks and eight nozzles were created and a local administrator account was set up.
- Compose started the app on 127.0.0.1:8000; an HTTP request returned the login page with status 200.

Local credentials are stored separately from this project and its ZIP.
This remains a local learning prototype, not production ready.

## Daily prices, salesperson dues and redesigned workspace

- All 20 tests passed with Python and again inside Docker after this upgrade.
- Verified daily-price locking, next-day price changes, per-nozzle half-up rounding,
  salesperson grouping, missing/inactive people, invalid rates, atomic rollback,
  and explicit labeling of older unpriced readings.
- Backed up the existing database before applying migration 0002.
- Docker image rebuilt, migration 0002 applied, and app restarted successfully.
- Browser verified the redesigned dashboard and live calculation:
  110.250 − 100.000 = 10.250 L; at Rs 102.375/L, amount due = Rs 1049.34.
- Browser checks did not save example readings or create fictional salespeople.

## Litre-only entry update

- Removed rupee-meter opening/closing fields from shift entry, reports and admin screens.
- New readings require litre meters, a salesperson and the day's rate; amounts due
  remain (closing litres - opening litres) × saved rate.
- Legacy rupee counters remain in the database; migration 0003 makes them nullable
  without deleting existing values. A database backup was saved before migration.
- All 22 tests passed inside Docker, including litre-only saves and continuing from
  older readings while preserving their historical rupee values.
- Migration 0003 applied and the running Docker app was updated.
- Browser confirmed the updated form has only opening/closing litre fields and
  existing saved shift data still appears. No example readings were saved during QA.

## Cash handovers and manager profiles

- All 39 tests passed inside Docker, including collections, shortage/excess,
  manager totals, required references, read-only duplicate protection, server-side
  expected-sales calculation, invalid inputs, login/CSRF and profile permissions.
- Added an exact-paise SQLite boundary test for Rs 0.10 + Rs 0.20 = Rs 0.30.
- Backed up the live database before applying migrations 0004 and 0005.
- Applied both migrations and restarted the updated Docker app successfully.
- Browser verified the handover list and collection form against the existing
  recorded shift. A temporary unsaved preview correctly calculated expected cash
  Rs 396088.34 and shortage Rs 88.34 from its entered collection breakdown.
- Created the real receiving-manager profile 'Durgesh' from the user's supplied name.
  Browser confirmed it is active and available in the Cash submitted to selector.
- No handover receipt or example collection was saved to the live database during QA.

## Paytm for Business and PhonePe Business

- Split new UPI entry into Paytm for Business and PhonePe Business fields.
- Old unsplit UPI receipts retain their original amount without assigning a provider.
- Both new provider fields are saved separately, included once in total UPI,
  and deducted once from expected cash. No external payment-account integration is implied.
- All 42 tests passed inside Docker, including provider validation, receipt display,
  legacy preservation and expected-cash calculations.
- Backed up the live database, applied migration 0006 and updated the running app.
- Browser confirmed Paytm Rs 1000 + PhonePe Rs 2000 reduced expected cash by Rs 3000,
  with a matching cash entry showing Balanced. These example amounts were not saved.
- Made the existing handover options explicit as Expenses and Debtor / credit sales,
  with guidance to record debtor names/slip references and expense vouchers in notes.

## Pandey Petrol Pump ledgers and lubes

All 46 tests passed inside Docker. Migrations 0007 and 0008 applied successfully after a live SQLite backup. Tests cover saved lube rates, separate petrol/diesel litres, linked credit and expenses, debtor repayment limits, handover locks and manager cash totals. Existing business data retained in the same Docker volume.

## Salary shortages
48 Docker tests passed including shortage deduction, duplicate prevention, rollback on insufficient salary, access control and rendering. Applied migration 0009 after backup.

## Separate station workspaces
50 Docker tests passed; station branding/selector tests also passed after final brand adjustment. Both containers use separate named volumes and session cookie names. Live read-only checks confirmed the original station retained its 8 readings, shift and other entries, while every pump model in the second station was empty. Only the owner administrator was initialized in station two.

## Single login organisation portal
53 full-suite tests passed before logout addition; all 6 organisation tests passed after it. Browser verified chooser, authenticated Shree Govind KSK handoff under /station2/, and return to chooser without another password. Signed ticket tampering and reuse are rejected. Sign-out handoff tested across both sessions. Nginx exposes one localhost port; both databases retained.

## Tank stock
58 Docker tests passed. Migration 0010 applied to both organisation databases after separate backups. Covered tank-specific fuel sales, delivery arithmetic, dip snapshot/variance, duplicate and invalid entries, closing locks, capacity validation and authenticated forms. Browser verified live stock dashboard without saving sample business entries.

## Daily closing report
Two targeted Docker tests passed for partial vs complete days, fuel totals, shortage, pending handovers, cross-date exclusion, auth and invalid/future date input. Browser verified actual daily sales and receipt totals, incomplete shift status and uninitialized stock labels. No business data changed.

## UI and demo workflow review
Desktop dashboard and organisation chooser visually checked; 390px mobile navigation opens correctly and exposes setup links, with offscreen navigation inert while closed. Nine targeted report/organisation/workspace tests passed. Workspace tested before/after settlement for prefilled links and locking. No live business entries changed.

## Expanded operations and superadmin
68 tests passed in Docker, including old regression tests and integrated operation flows. Migrations 0011-0014 applied in both organisation databases after backups. Added a new superadmin in each database without changing existing user passwords. Tax and discounts remain disabled. No sample financial operations were inserted in the live databases.

Superadmin live verification: both accounts active/staff/superuser, every Django permission granted, admin and operations return HTTP 200. Existing primary readings/handovers remain 8/1; second station remains 0/0. New income and sales receipt counts remain zero in both. No model migration drift detected.

## Top-bar organisation switcher
Eight organisation tests passed, including secondary-to-primary signed sign-in, shared switcher rendering in application/admin and denied cross-organisation escalation for ordinary staff. Browser verified switching from stock to the second organisation and back using the dropdown.

## Supplier accounts
74 full-suite Docker tests passed, including invoice/receipt quantity differences, cost/freight totals, partial payments, supplier credits, overpayment rejection, reversal retention, dates, duplicates, forms and permissions. Migration 0015 applied to both databases after separate backups. Browser confirmed empty supplier accounts without adding sample business data.

## Full-work review
77 tests passed. Thirty authenticated route checks and SQLite integrity/foreign-key checks passed across both organisations. No handover-snapshot differences or negative tracked lube stocks found. Fixed allocation/cash-return interactions, partial-receipt rounding, and configured a private local signing key excluded from package/build context. See ALL_WORK_REVIEW.md.

## Dashboard graphics
Added seven-day volume/revenue charts, collection mix and tank gauges with honest empty states. Both new data/rendering tests passed; the 79-test regression suite passed. Tests verify missing-date distinction, actual handover totals, normalized shares, saved-sale totals, tank stock percentage and low-stock markers. Live Chrome visual check completed after user sign-in: verified desktop charts, volume/revenue switching, exact daily figures, collection totals, unset-stock messages and stacked chart panels at 390px. No business entries were changed.

## Encrypted backups and recovery
86 full-suite Docker tests passed (including seven backup/access/recovery tests). Tests cover restoration of both isolated databases and uploads, record counts, source/private settings, wrong keys, corruption, archive traversal, missing-station failure, secondary-copy failure/retry, and incompatible schema rejection before replacement. Live bundles passed decryption, checksum, integrity, foreign-key and record-count checks. Primary/secondary encrypted file hashes matched. Windows ACLs verified owner/SYSTEM/Administrators only. Chrome owner screen and manual backup request checked. PowerShell verify-only rehearsal succeeded on a live-data bundle; operational databases were not replaced. Automatic hourly scheduling runs inside Docker, with startup backup and manual requests. Separate-disk protection is not configured; both folders are local. Full replacement-PC rebuild remains untested.

## Operational controls and reconciliation
102 full-suite tests passed. No migration drift. Migrations 0016-0022 applied to both databases after verified backups. Added assigned staff roles, audited daily submit/review/close/reopen, SQLite date-lock triggers, cash/bank subledger and transfers, bank allocations/corrections, two-step normalized payment evidence CSV imports, read-only debtor ageing and tank quality observations. Coverage includes stale reviews, owner exceptions, raw/bulk lock rejection, complete-day manager close, role endpoint restrictions, transfer double-entry conservation, no repeated shift-expense deduction, net settlement posting, account correction, idempotent imports, exact matching and historical ageing. Live accounts, balances, observations and closing states were not fabricated. See CONTROLS_AND_RECONCILIATION.md for remaining scope and operating limits.

## Setup readiness and isolated pilot
104 tests passed, including an integrated two-shift synthetic pilot across stock, lube sales, credit/repayment, cash/expenses, provider evidence, bank settlement, deposit, quality measurements and approved closing. Owner-only setup readiness rendering/access tested. Actual station configuration audited read-only; absent balances/measurements and demo equipment remain explicitly unverified. See PILOT_SETUP_STATUS.md.
