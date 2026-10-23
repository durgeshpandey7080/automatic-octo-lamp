# Pandey Petrol Pump — local Django learning project

Repository: https://github.com/durgeshpandey7080/automatic-octo-lamp

This is the source checkpoint imported on **23 October 2026**, including two-station operation, owner dashboard, reconciliation, payroll/advances, shortage recovery, local AI and the optional English/Hindi interface. Feature-specific limitations remain in the process documents below.

**Start here:** [repository import and isolated verification](docs/REPOSITORY_IMPORT.md). The original setup scripts below target the existing `hpcl_pump` installation; read the import notes before running them from a second checkout. Private business data and credentials are not in this repository.

**Owner dashboard redesigned:** [delivery and verification](docs/REDESIGN_STATUS.md), [agreed requirements](docs/DESIGN_BRIEF.md), and [remaining implementation plan](docs/REDESIGN_PLAN.md). The first phone dashboard includes fuel sales, same-weekday comparison, cash, configurable tank warnings and a review section. Broader cash-custody and shift-submission workflows remain planned. The separate progress website source is in [docs/project-report-site](docs/project-report-site).

A working starting point for one Windows computer and one operator: 8 nozzles,
2 daily shifts, cumulative litre meter readings, daily fuel prices,
and amounts due by salesperson. This is **not production
ready**, an official HPCL product, or an HPCL-connected application.

## Recommended: Docker containers on Windows

Install Docker Desktop for Windows from https://docs.docker.com/desktop/setup/install/windows-install/.
Use its WSL 2 backend and Linux containers, complete any requested Windows restart,
and start Docker Desktop. No Windows Python installation is needed for this option.
Extract this project and open PowerShell in the folder containing `compose.yaml`.
Run each command in order:

```powershell
docker --version
docker compose version
.\setup-local.ps1
docker compose build
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py createsuperuser
docker compose run --rm web python manage.py seed_demo
docker compose up -d
docker compose logs web
```

`seed_demo` is optional: it creates invented tank/nozzle assignments. Adjust them
in admin before recording readings, or skip it and create your actual configuration.
Open http://127.0.0.1:8000/ and sign in. Admin is at http://127.0.0.1:8000/admin/.
The container runs the same local development server and is not production ready.

For later starts and stops:

```powershell
docker compose up -d
docker compose stop
```

Run the checks inside a disposable container:

```powershell
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py makemigrations --check --dry-run
docker compose run --rm web python manage.py test
```

The named `pump_data` volume persists the database across container replacement.
Docker and native Python use separate database files; they do not automatically
share records. Keep the same extracted project folder so Compose uses the same
project/volume name. `docker compose down` removes containers but preserves data;
**do not use `docker compose down -v`**, which deletes the database volume.
After changing source files, run `docker compose build` then `docker compose up -d`.
Apply new migrations with the migration command above.

To back up Docker data, stop the server, copy the database from the stopped
container, then start it again. Run these from the project folder:

```powershell
docker compose stop web
New-Item -ItemType Directory -Force backups
$backupStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
docker compose cp web:/data/db.sqlite3 "./backups/db-$backupStamp.sqlite3"
docker compose start web
```

Keep backups private and outside shared source archives. To test restoring into a
separate project copy with a different folder name: build it, run `migrate` to
initialize its own volume, run `docker compose create web`, then use
`docker compose cp ./backups/YOUR-BACKUP.sqlite3 web:/data/db.sqlite3` while its
server is stopped. Start that copy and verify the records. Never restore over
your only live database without a separate backup.

If Docker cannot connect to its engine, start Docker Desktop and wait until it
reports running. If port 8000 is occupied, change the Compose port mapping to
`127.0.0.1:8001:8000`, run `docker compose up -d`, and visit port 8001.

The sections below explain the alternative native Python setup and application.

## 1. Install Python and open PowerShell

Install Python 3.13 for Windows from https://www.python.org/downloads/windows/.
Include the Python launcher during installation. Close and reopen PowerShell.
Check:

```powershell
py -3.13 --version
```

If `py` is not recognized, repair your Python installation and enable the launcher.
Python 3.13 is supported by Django 5.2; see
https://docs.djangoproject.com/en/5.2/releases/5.2/.

## 2. Extract and enter the project

Extract the supplied ZIP into a folder such as `C:\HPCLPump`. Open the folder
containing `manage.py` in File Explorer, right-click, and choose **Open in Terminal**.
Alternatively, use the real path to that folder:

```powershell
Set-Location 'C:\HPCLPump\hpcl_pump'
Get-ChildItem
```

You should see `manage.py`, `requirements.txt`, `config`, and `pump`.
Do not run `startproject`: the project files are already included.

## 3. Create an isolated Python environment and install Django

Run each line in order. The explicit Python path avoids PowerShell activation-policy problems.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m django --version
```

The last command should print `5.2.18`. Internet access is needed for installation.
The project pins this Django 5.2 patch for reproducibility.

## 4. Create the local database and account

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Choose a username and a strong password. Password characters are hidden while typing.
`migrate` applies the included migration files and creates `db.sqlite3`.
No separate database server is needed.

For a quick learning setup, create two **demo** 20,000-litre tanks, with nozzles
1–4 assigned to petrol and 5–8 assigned to diesel:

```powershell
.\.venv\Scripts\python.exe manage.py seed_demo
```

These are invented example assignments and capacities. Before entering readings,
open Administration and change them to your actual pump configuration. The seed
command refuses to change a nonempty database. Alternatively, skip it and create
your tanks and exactly eight nozzles numbered 1 through 8 in Administration.

## 5. Run locally

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Keep PowerShell open. Visit http://127.0.0.1:8000/ and sign in with your new account.
Administration is at http://127.0.0.1:8000/admin/.
Stop the server with Ctrl+C. If port 8000 is busy, use `127.0.0.1:8001` and visit
that port instead. On later days, return to the project folder and repeat only
the `runserver` command. This is a local development server.

## 6. Record a shift

1. In Administration → Salespeople, add your actual staff names. Mark departed staff
   inactive rather than deleting people linked to past readings.
2. Start with Shift 1 on your chosen first business date (today or a past date).
3. Enter that day's petrol/diesel price in rupees per litre, for each fuel you use.
   Prices are entered manually, not fetched from HPCL.
4. Assign a salesperson to each nozzle and enter cumulative opening and closing
   litre totals. One person can handle multiple nozzles.
5. Review the live litres and amount-due previews, then save all eight together.
6. Review the daily **Amount due by salesperson** table and expand shifts in history.
7. Enter Shift 2 for the same date, then Shift 1 for the next date.

Litres sold = closing litres − opening litres. Amount due = litres sold × the
fuel's daily price. Each nozzle amount is rounded to paise using ROUND_HALF_UP;
person and daily totals sum those rounded amounts. Example: 150.250 litres at
Rs 100.00/L gives Rs 15,025.00 due from the assigned person. The entry screen needs only opening/closing litre readings, a salesperson, and the daily rate.

**Amount due is gross fuel sales, not cash received or a final settlement.** It
does not deduct credit sales, card/UPI collections, expenses, testing fuel, or
advances. Record collections separately in **Cash handovers**, described below.

The first saved shift locks prices for that date; Shift 2 must use the same prices.
Each reading stores a price snapshot so tomorrow's prices cannot change past dues.
Intraday price changes are not supported. Confirm prices before saving.

The dashboard shows the latest **recorded business date**, which can differ from
today. Staff totals include saved shifts on that date only. Draft previews do not
alter recorded totals. Older readings without prices/staff are preserved and marked
unpriced/unassigned; affected totals are explicitly labeled partial.

After the first shift, openings are prefilled from the previous closing. They
must match exactly. Dates cannot be in the future. There are no skipped shifts;
if closed for a shift, enter unchanged readings, giving zero sales. Shift 2 belongs
to the same business date even when it ends after midnight. No start/end clock
times are modeled yet.

Example for a single nozzle: litres 125000.000 → 125150.250 gives 150.250 litres.
At Rs 100.00/L, the amount due is Rs 15,025.00. Repeat with actual readings for the
other seven nozzles. Readings accept up to 13 digits before and 3 after the decimal
point. Enter digits and a decimal point without commas or currency symbols.
Calculated dues are rounded to two decimal places.

Rupee-meter opening/closing fields were removed from entry and reports. New readings
leave the legacy database columns empty; any historical rupee counters are preserved.

## 7. Record cash submitted to a manager

1. Open **Manager profiles → Add manager** and enter the real manager's name.
   Phone and profile notes are optional. Only accounts with the Django manager-profile
   add/change permission can create/edit profiles; your superuser account has it.
2. Open **Cash handovers**, select a completed shift, and click **Record handover**
   for the salesperson. The salesperson can be inactive now if they worked that shift.
3. Select the receiving manager in **Cash submitted to**.
4. Enter cash submitted, card collections, Paytm for Business and PhonePe Business.
   Debtor credit and shift-cash expenses are calculated from separate records; these fields are disabled.
5. Add references for credit slips/expense vouchers and explain any shortage/excess.
   The **Debtor / credit sales** field is the amount customers owe; include their
   names or slip references in notes. **Expenses** is cash paid out of this shift.
6. Check the preview and click **Record cash handover**. The saved receipt is read-only.
7. Open the manager's profile to see the total cash submitted to them and latest
   20 receipts across all business dates. Totals include cash only, not card or UPI.

Expected cash = gross sales − card − Paytm for Business − PhonePe Business − credit sales − expenses from shift cash.
Difference = actual cash submitted − expected cash. A negative difference is a
shortage; positive is excess; zero is balanced. Example: sales Rs 7,600 less card
Rs 1,000, Paytm Rs 400, PhonePe Rs 600, credit Rs 500, expenses Rs 100 gives Rs 5,000 expected cash.
If Rs 4,900 is submitted, the shortage is Rs 100. Collections (cash + card + UPI)
are separate from credit/expense adjustments; credit is not money collected.

The server recomputes gross sales from the saved priced readings; it does not
accept a client-supplied sales total. A handover requires a complete eight-nozzle
shift with staff and prices, and a currently active receiving manager. At most one
receipt can be saved per shift/salesperson. Card + UPI + credit + expenses cannot
exceed gross sales. Use authorized expenses only and verify payment/credit references
yourself; this prototype does not validate bank transactions or expense approvals.

Paytm for Business and PhonePe Business are manual collection entry fields, not
connected merchant accounts. Both are included once in total UPI and deducted once
from expected cash. Older unsplit UPI receipts retain their amount under
"Earlier UPI (provider not recorded)"; no provider is invented for past collections.

Manager profiles are a directory of cash recipients, not separate sign-in accounts
or a manager approval system. Deactivate a manager to prevent new receipts while
preserving history. Profiles can be edited; existing receipts show the current
profile name. The recorder's account and time are retained on each receipt.
No real money is transferred by saving a handover. Deposit reconciliation and a correction workflow for saved receipts are not implemented.

## 8. Lube products, expenses and debtor accounts

The software is named **Pandey Petrol Pump**. Dashboard and handover summaries show
petrol litres and diesel litres separately. Lube sales are shown separately in rupees
because products may use different units.

1. Open **Lube products & sales**, add each actual product name (include its pack
   size), unit and selling rate. Record a sale against a saved shift and salesperson.
   Selecting a product fills its current rate; confirm quantity and rate before saving.
   Every sale keeps its own rate, so later product-price changes preserve past amounts.
2. Open **Debtor accounts** to create actual customers, optionally with an opening
   balance. Record credit sales against the shift and salesperson. These increase the
   customer balance and automatically reduce that person's expected shift cash.
3. Record debtor repayments on the customer's page with method, receiving manager
   and unique reference. Payments reduce the balance; overpayments are rejected.
   Enter each customer's transactions in date order. Repayments do not change current
   shift sales. Only cash repayments increase the manager's total cash received.
4. Open **Expenses** and record a voucher, category, payee, description and amount.
   Choose **Shift cash** and the appropriate shift/person to deduct that expense from
   their handover. Station cash, bank, Paytm and PhonePe expenses remain separate.
5. Record all lube sales, credit sales and shift-cash expenses **before** saving the
   cash handover. Saving it locks further linked entries for that person and shift.
   Credit and expense totals on the handover are automatic, avoiding double entry.

Gross sales = saved fuel sales + saved lube sales. Expected cash = gross sales minus
card, UPI, debtor credit and shift-cash expenses. Older handovers retain their saved
aggregate adjustments; they are not converted into invented customers or vouchers.
Lube stock, purchasing and inventory valuation are not included. Used products retain
 their unit; use a separate product for a different pack size or unit.

## Architecture and files

Browser → URL route → authenticated view → forms → transactional save service → SQLite.
The view renders Django HTML templates. JavaScript adds previews; server calculations
and validation still work without it.

```text
manage.py                    Django command entry point
requirements.txt             Django version
config/settings.py           Local SQLite, timezone, login and middleware
config/urls.py               Admin, login/logout and pump routes
config/wsgi.py               Standard Django WSGI entry point
pump/models.py               Station models, prices, staff, ManagerProfile and Handover
pump/migrations/0001_initial.py  Database tables and constraints
pump/migrations/0002_*.py     Prices and staff; preserves older readings
pump/migrations/0003_*.py     Makes legacy rupee counters optional
pump/migrations/0004_*.py     Manager profiles and cash handover receipts
pump/migrations/0005_*.py     Paise-accurate adjustment comparison in SQLite
pump/migrations/0006_*.py     Separate Paytm and PhonePe collections; retain old UPI
pump/migrations/0007_*.py     Debtor accounts, payments and expenses
pump/migrations/0008_*.py     Lube products and saved sales
pump/forms.py                Shift form and eight-row reading formset
pump/services.py             Consecutive shifts, continuity, atomic save
pump/views.py                Entry screen and recent history
pump/urls.py                 Home route
pump/admin.py                Configuration and read-only ledger
pump/tests.py                Validation, database, security and request tests
pump/test_handovers.py       Collections, manager profiles and handover tests
pump/management/commands/seed_demo.py  Optional example configuration
pump/templates/pump/         Shared layout and entry/history screen
pump/templates/registration/login.html  Login screen
pump/static/pump/app.css      Dashboard, entry and login styling
pump/static/pump/entry.js     Live previews using exact integer arithmetic
pump/static/pump/handover.js  Cash due and shortage/excess previews
```

One tank supplies many nozzles. A shift has a unique business date and number
(1 or 2). Each reading joins one shift to one nozzle and stores opening/closing litre
totals, a salesperson, and a saved unit price. DailyFuelPrice is unique by date and
fuel. Unique and check constraints protect basic database invariants. Form/model
validation checks numeric input and decreasing readings. The service checks all
eight nozzles, shift order and meter continuity, then saves everything in a single
transaction. A failure rolls back all eight rows and the shift.

Use `save_shift()` and `save_handover()` for any future import or API: raw ORM writes do not automatically
run model validation or the service's cross-shift rules. The admin ledger is
read-only to prevent isolated changes that break that chain. Used nozzles cannot
be remapped through admin, and a used tank's fuel type cannot be changed. Tank
names/capacities and salesperson names remain editable as live configuration.

## Tests and checks

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test
```

Tests use a temporary test database and do not erase your local ledger. Included
migrations should produce `No changes detected`. When you intentionally change
models later, run `makemigrations` and then `migrate`.

## Data, limitations and next steps

Stop the server before copying `db.sqlite3` to a dated backup location. Protect
that file: it includes accounts and business records. Test a backup by restoring
it into a separate project copy. Do not share your live database in a ZIP.

This prototype is for one trusted local operator. All signed-in users can enter
readings and cash handovers, and view manager profiles. Profile creation/editing
requires Django permissions. There are no individual station/operator restrictions. SQLite and this workflow
are not designed for simultaneous operators. Saved readings cannot be corrected
through the UI. If you make an error, stop further entry and have a developer plan
a validated correction; do not directly edit the database. Meter resets,
rollovers and replacements are rejected and need a separate audited workflow.

There is no testing-loss reconciliation,
bank verification, billing, tax reports, full audit trail, intraday pricing,
HPCL/device integration, deployment security or automated backup. Tank stock requires actual opening balances and delivery records; dip variance is not automatically reconciled. Calculated sales amounts
are not proof of money collected. Next development steps should
include verified correction/audit handling, stock reconciliation and correction handling.
Do not expose this DEBUG-enabled project to the internet or use it as your sole
operational or accounting record.

## Fixed monthly salaries and shortages

Staff administrators can open Salaries & shortages and record each person's actual fixed monthly salary. The server deducts all saved, undeducted handover shortages through that month, including older pending shortages. Each handover links to only one deduction. Excess does not offset shortages. One read-only salary calculation is allowed per person/month; enter months in order. Later shortages remain pending for the next salary. Negative salaries are rejected when shortages exceed salary. This records net salary due, not salary payment. No salary amounts are invented.

## One login and organisation selection

Open http://127.0.0.1:8000/login/ and sign in once with the existing owner admin.
Choose Hamara Pump Narai or Shree Govind KSK on the organisation screen. Use
Switch organisation inside the workspace or admin to return to that screen.
Both organisations use the same software address. Shree Govind KSK runs under
/station2/. Port 8001 is no longer used. Logout signs out both organisation sessions.

Each organisation retains its own Docker volume/database. Existing records stay
in Hamara Pump Narai; Shree Govind KSK starts empty. Configure its actual tanks,
eight nozzles, salespeople and manager before recording shifts. The owner admin
account exists in both databases; ordinary staff access is not assigned automatically.
Adding other users or changing passwords across organisations needs coordinated
account management. This local prototype's organisation handoff is restricted to
the owner administrator; it is not a full organisation-membership system.

For a fresh installation:
```powershell
.\setup-local.ps1
docker compose build web
docker compose run --rm web python manage.py migrate
docker compose run --rm station2 python manage.py migrate
docker compose run --rm web python manage.py createsuperuser
docker compose run --rm station2 python manage.py createsuperuser
docker compose up -d
```
Use the same owner username in both workspaces. The running installation already
has its owner initialized. Nginx routes the one address to the two organisation
workspaces. Short-lived, single-use signed tickets perform the organisation handoff;
passwords are not sent when switching. Each organisation keeps separate session cookies.
Back up web and station2 separately using the earlier backup commands. Their
volumes are pump_data and station2_data. Keep the Compose project name hpcl_pump
on this computer to reuse existing volumes. Do not use down -v. Apply future
migrations to both services. Native Python supports one workspace; use Compose
for the complete portal. This remains a local learning prototype.

## Tank stock, deliveries and closing dips

Open Tank stock in the selected organisation. Confirm actual tank capacities and
nozzle mappings before using stock calculations; existing DEMO configuration is
not verified physical equipment.

1. Set actual opening litres once per tank, at the START of the chosen business
   date. Sales before that date are excluded; sales and deliveries on it are included.
2. Record litres actually received, supplier and unique invoice/reference per tank.
   For a delivery split across tanks, use distinct references such as invoice/tank.
3. Save shift readings as usual. Book stock = opening + deliveries - saved nozzle
   litre sales from that tank. Missing shifts mean the balance is incomplete.
4. After Shift 2, enter the closing dip in calibrated LITRES. The system snapshots
   expected stock and shows physical minus expected variance. No dip-height-to-litre
   conversion is assumed. Dips compare stock; they do not reset or reconcile it.

A saved closing dip prevents later deliveries on or before that date. Enter all
that day's deliveries before closing. Future entries, duplicate openings, zero
or negative deliveries and physical quantities beyond capacity are rejected.
Calculated balances outside zero/capacity display a warning and require review.
Stock entries are read-only after saving; correction, testing losses, water/dead
stock, temperature compensation and purchase accounting need further development.
No actual opening stock or deliveries have been invented in the live databases.

## Daily closing report

Open Daily closing report in the chosen organisation. Select a business date and click Show report; Print report opens browser printing. Sales use saved litre/rate snapshots plus lube sales. Collections cover only saved handovers. Missing handovers and missing shifts keep the day incomplete. Two shifts, sixteen priced/assigned readings and all handovers are needed for sales/handovers complete. Stock completeness is separate. Repayments are separate from sales. Expenses by source are informational and must not be deducted twice. This live report does not lock the day or post accounting entries. No CSV or final close snapshot is included.

## Updated interface and Shift workspace

Navigation groups Daily work, Accounts and Station setup. The organisation chooser is separate from station navigation; the phone layout has a collapsible drawer. Open Shift workspace to select a saved shift, see each salesperson totals and add lube, credit and expense entries with shift/person prefilled. After handover, those entry links are hidden and the saved receipt remains available. VIDEO_REVIEW.md documents the reference demo, what exists and what remains to build.

## Expanded operations

The seven-point first-video backlog is implemented within the agreed scope, with tax/discount computation deliberately disabled. Use OPERATIONS_GUIDE.md for drafts, returned testing, credit details, income/digital vouchers, lube inventory, cash/bank matching, ordinary sales receipts and automatic numbering. SECOND_VIDEO_NOTES.md records additional ideas; those recommendations are not claimed as implemented. The superadmin account has access to both organisations. Its credentials are saved separately outside the source archive.

## Switch organisation from the top

Click the organisation name in the top bar and select the other station. The selector is available in application and admin screens. Switching opens the target organisation overview, without another password, and uses the existing owner-access checks. Save unfinished forms before switching. The current organisation is marked in the menu.

## Supplier accounts and fuel purchase settlements

Open Supplier accounts. Add the actual supplier, then link its invoice to a fuel
delivery already recorded in Tank stock (the delivery table also has a direct link).
Enter billed litres, unit cost and freight billed by that supplier. Purchase cost
uses billed litres; received stock remains the actual delivery quantity. This does
not add stock a second time. Internal PUR numbers are generated automatically;
the external supplier invoice number remains manual.

Record partial/full payments against an invoice. SP payment numbers and SC credit
note numbers are automatic. Noncash payments require the actual external transfer
reference. Overpayments, duplicate active invoices/delivery links and invalid dates
are rejected. Only an actual supplier-issued credit note reduces payable for a
shortage; the quantity variance alone does not. Reverse mistakes with a reason:
original records and audit events remain. Void linked payments/credits before
voiding an invoice. Reversing financial entries does not change tank stock.

Daily reports show supplier payments separately. Do not duplicate them as shift
expenses; no cash transfer or bank payment occurs when recording them here.
Supplier advances, refunds, multi-tank invoice grouping, transporter accounts and
a full double-entry cash/bank book are not implemented. Existing free-text delivery
supplier names were not converted into invented account balances. Tax/discount
calculations remain disabled.

## Installation signing key and review

Before first Docker startup in a fresh extraction, run .\setup-local.ps1 from
PowerShell. It creates .env only if missing and retains an existing key. If script
execution is blocked, use powershell -ExecutionPolicy Bypass -File .\setup-local.ps1
for this local script. Keep .env private and outside shared archives; preserve it
with private deployment settings. A key change expires old login sessions but does
not remove accounts or business data. Both station containers share that key.
The native single-station fallback still uses a local development key unless
PUMP_SECRET_KEY is provided. See ALL_WORK_REVIEW.md for the current review and limits.

## Dashboard graphics

The overview now includes a seven-day petrol/diesel litres chart, a sales-value
view, a collection-mix bar with exact amounts and tank-level gauges. The window
ends on the latest recorded business date shown on the dashboard. Missing days
show dashes instead of assumed zero sales; recorded zero-sale days remain distinct.
The exact daily figures are available in an expandable table.

Collection mix includes saved handovers only. It excludes debtor credit and
expenses, and cash includes any recorded float/return effects. It is not a pie of
gross sales or a bank balance. Stock gauges show calculated stock through the
same business date, not physical dip readings. Tanks without openings remain
unfilled and labelled. A warning marks calculated stock at/below 20% capacity;
it is a visual reference threshold, not an automatic purchase order.

## Automatic encrypted backups
Run `setup-local.ps1` (or `setup-backups.ps1` for an already configured install) before starting Compose. Both station databases, source/private settings and persistent uploads are backed up hourly while Docker runs. The superadmin **Backups & recovery** page shows successful backups, restore rehearsals and second-copy failures. Two protected folders are created alongside the project; both remain on this PC. Save the private recovery key separately, and copy encrypted bundles to an external drive for disk-loss protection. See [BACKUP_RECOVERY.md](BACKUP_RECOVERY.md) for retention and safe PowerShell verification/restoration. No live rollback has been performed.

## Operational controls and reconciliation
New menus: **Approve daily close**, **Staff permissions** (owner only), **Cash & bank book**, **Payment report imports**, **Debtor ageing**, and **Density & water checks**. Read [CONTROLS_AND_RECONCILIATION.md](CONTROLS_AND_RECONCILIATION.md) before use. Existing login roles and real balances were not changed automatically. Enter actual opening balances, assign staff roles deliberately, and use normalized CSV payment evidence until native provider exports are verified. Closed periods are protected by SQLite triggers; only the owner can reopen with a reason. These modules remain a local development prototype.


## Latest update: 19 October 2026
Tax remains disabled; owner-approved flat-rupee shift discounts are now enabled. This supersedes older statements that discounts are disabled. See SALARY_AND_DISCOUNTS.md for salary adjustments, duplicate protection, discount reversal, daily workbench and nozzle bulk allocations. Both organisations contain demonstration data, confirmed by the owner. Latest tests: 112 passed; migrations through 0026.


## Salary payment workflow
See SALARY_PAYMENT_PROCESS.md. Actual cash/bank salary-payment records, partial payments, outstanding balances and reasoned reversal are now available to the owner. Advances and actual shortage recovery/refunds remain unfinished. Latest verification: 116 tests; migrations through 0028.


## Staff advances
Owner-only staff advance records and explicit partial/monthly salary clearing are now implemented. See STAFF_ADVANCES_PROCESS.md. Advances create one cash/bank outflow; applying to salary creates none. This supersedes older advance backlog notes. Latest verification: 122 tests passed; migration 0030. Actual refunds/cash recovery and employee acknowledgement remain future work.


## Shortage recovery (20 October 2026)
Sidebar: Shortage recovery. See SHORTAGE_RECOVERY_PROCESS.md for receipt, payroll and correction rules. Migration 0032; 127 tests passed. Original shortage history is retained; later receipts credit money and release the linked salary deduction once. Tax remains disabled; discounts enabled.


## Combined owner dashboard (20 October 2026)
Owner sidebar/organisation chooser → Both stations · Owner dashboard. See OWNER_DASHBOARD_PROCESS.md. Both services exchange signed read-only summaries while keeping databases separate. Docker Compose configures OWNER_SUMMARY_PEER_URL; without it the remote station is marked unavailable. 138 tests pass; no new migration (latest 0032). The view shows dated sales, recorded balances and pending items, not live bank confirmation.


## Local AI briefing (22 October 2026)
Owner-only local Qwen3/Ollama prioritises verified checks in English/Hindi; facts and amounts stay application-calculated. See LOCAL_AI_PROCESS.md and setup-local-ai.ps1. No model tools or financial edits. The isolated AI container has no published port or internet route in normal operation. The initial free-form narration was rejected after factual errors; only validated check IDs are now accepted. 146 automated tests pass.
