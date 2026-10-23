# New controls and reconciliation screens

These additions are installed independently in both organisations. No sample financial records, account balances, staff-role assignments, quality measurements or actual day closes were inserted into live data during development.

## Staff permissions

The owner superadmin opens **Staff permissions** and selects an existing local login. Create a login through Django Administration first if needed; passwords are not displayed by the permissions page.

- Cashier: may save shifts, open duties, submit handovers, enter credit slips and lube sales, and submit a day for review. Salaries, suppliers, money book, payment imports, user administration and backups are blocked. Operational read access is station-wide, not limited to one salesperson.
- Manager: operational entries, money transfers, bank assignments, payment-evidence imports and daily review/close. No Django admin, user-role changes or backup access.
- Accountant / Viewer: read-only app access. Existing salary screens retain their separate staff restriction. These roles cannot submit financial changes.
- Disabled access: no station pages except logout. The account is not deleted.
- Owner: complete access, role assignment, reasoned reopening and exception overrides.

Existing accounts labelled `LEGACY_MANAGER` or `LEGACY_CASHIER` retain their previous behaviour until the owner explicitly assigns a role. No existing login was silently restricted. Review legacy users before staff rollout. Role assignments are local to a station; ordinary users do not acquire cross-station access. Superadmin access continues to cover both organisations. Role changes are audited. Assigned managers are marked staff for existing service checks, but middleware still denies their Django-admin routes.

## Daily closing

Open **Approve daily close**, choose a date, and inspect the exception list and actual totals.

1. **Submit for review** saves a fingerprint of relevant records and a summary snapshot.
2. A different manager records review. The owner may self-review only with a reason.
3. **Close and lock day** is available after review. Changes since submission/review require resubmission.
4. Missing shifts/readings/handovers, open duties, missing or abnormal stock, cash differences, and missing/review-needed quality observations remain visible. A manager must resolve them. Only the owner can close with a recorded exception explanation of at least ten characters.
5. Reopening requires the owner, a reason and reopening later closed dates first. Submit/review/close again after correction.

SQLite triggers protect INSERT, UPDATE and DELETE for dated operational ledgers, including bulk operations. Normal saves also give friendly validation. Entries at or before the latest closed date cannot be changed or backdated. A later bank settlement is permitted on its own open settlement date, even when the collection's business day is closed. Closed-period stock openings, money-account openings and allocations also require reopening before change. The SQL triggers are SQLite-specific and must be ported before changing database engines.

The printed daily report remains a live operational report; the closing screen separately retains the approved summary, fingerprint, actors, reasons and audit events. This is not statutory accounting certification. Master-data edits can invalidate an unclosed review; review again after configuration changes. A close with owner-approved exceptions is not labelled fully reconciled.

## Cash and bank book

The owner must first enter actual account balances **at the start** of a chosen opening date. Earlier movements are excluded from that baseline. One pooled station cash account is supported, with multiple named bank accounts. Cash cannot have a negative opening; bank overdrafts may be recorded. Opening records are immutable in the UI; corrections need a controlled review, not a silent overwrite.

The cash statement includes actual salesperson cash handovers, office-to-staff floats/cash receipts as outflows, staff cash returns, station-cash expenses, cash debtor repayments and cash supplier payments. Shift-cash expenses have already reduced cash actually handed over and are not deducted again. Other income and lube sales already collected through handovers are not counted as additional cash receipts.

Bank movements come from existing net settlement matches, bank expenses, debtor bank repayments and supplier bank payments. Assign each to its real bank using the labelled movement list. Unassigned movements remain visible and excluded from bank balances. Incorrect bank assignments can be corrected by the owner with a reason; the prior assignment is retained in audit history. A closed date must be reopened first.

Record a deposit, withdrawal or bank-to-bank transfer once using source/destination accounts. The system creates an equal outflow and inflow, with an automatic internal number, actual external reference and notes. This creates no income or expense. Duplicate active external references and identical source/destination accounts are rejected. Transfers cannot precede either account's opening date. Recorded station cash must cover a new outgoing transfer. Bank accounts may go negative; verify real overdraft arrangements yourself. Owner reversals retain records and reasons and are blocked in closed periods.

Statements have an ordered date filter and CSV export. CSV text cells are escaped against spreadsheet formula interpretation. Balances reflect recorded and assigned movements, not a live bank connection. There is no full general ledger, payroll-payment posting, owner capital/drawings journal, automatic bank-statement import or per-manager physical cash book yet. Digital-wallet expenses and repayments require provider reconciliation separately.

## Payment-report evidence imports

**Payment report imports** accepts a normalized UTF-8 CSV using these headings:

```csv
reference,date,amount,status,description
```

Select Paytm Business or PhonePe Business and enter the actual merchant identifier. Keep merchant accounts separate. Dates are business dates in `YYYY-MM-DD`; amounts are positive rupees with at most two decimal places; status must be `SUCCESS`. The download supplies headings only, with no fake transactions. Map a copy of the original provider export; native Paytm/PhonePe column formats have not yet been verified against the user's files. Pending, failed, refunded and reversed rows must be reviewed separately rather than misclassified as successful collections.

Preview first; confirm to store evidence. Maximum file size is 2 MB / 10,000 rows. Confirmation is transactional. Repeating a file is idempotent; overlapping identical transactions are skipped. A reference with conflicting date/amount rejects the entire file. Originals remain with the operator; the database stores the file checksum, normalized evidence, importer and counts. Preview is stored in the current server-side session until confirmed/discarded; invalid replacement uploads clear the old preview.

Exact collection candidates are shown. Matching requires provider, reference, amount, date and any recorded merchant identifier to agree. A collection/evidence row can be matched once. Matching or importing does **not** create a sale, collection, bank credit or bank settlement. A bank match remains a separate existing workflow. Manual digital amounts entered only on handovers are not covered by record-level evidence matching. Live APIs, native report adapters, refund workflows, bank-statement matching and automated many-to-one settlement allocation are not implemented.

## Debtor ageing

**Debtor ageing** is a read-only oldest-first estimate with an as-of date, customer links, print and CSV export. It applies recorded repayments against the oldest opening/credit rows for reporting, without changing transactions. Buckets are 0–30, 31–60, 61–90 and over 90 days. Inactive debtors with outstanding balances remain included.

Age starts at the recorded opening or credit date. Opening balances may contain older debt whose original dates are unknown. These are not contractual overdue buckets: credit terms, credit-limit overrides and saved bill-by-bill repayment allocations are still future work. Historical as-of reports exclude later repayments.

## Tank quality observations

**Density & water checks** records actual morning and after-delivery observations: tank, business date, actual observation time, observed density in kg/m³, temperature in °C, optional verified density at 15°C plus correction reference, measured water dip in mm and notes. Entry timestamp/operator are recorded separately. After-delivery observations must match the selected tank, delivery and date. Duplicate active morning/delivery observations are rejected. Owner reversals retain audit history; closed dates require reopening.

The software does not calculate temperature corrections, invent measurement tolerances, certify quality or control a dispenser. The operator must use verified instruments/tables and applicable company procedures. A positive water reading is highlighted for investigation. Daily close flags missing morning/delivery observations, positive water or missing density-at-15°C values as exceptions. Tanker compartment/seal records, calibrated dip-chart conversion, compliance deadline tracking and full delivery-inspection checklists remain future work.

## Validation and limits

102 Django tests pass, including closing transitions, exception overrides, self-review, stale reviews, closed-period raw/bulk write rejection, complete-day closing, role endpoint restrictions, cash/transfer arithmetic, no double expense deduction, net settlements, bank assignment/correction, CSV import previews/idempotency/conflicts, exact evidence matching, historical debtor ageing and quality validation. Migrations through 0022 are installed in both station databases. Live financial records were retained; no live business day was closed or reopened for a demonstration.

This remains a local development prototype using Django's development server and DEBUG. These additions do not make it production ready. Tax and discounts remain disabled. Existing salary calculations have not been replaced with a wage-deduction approval/payroll-payment ledger.
