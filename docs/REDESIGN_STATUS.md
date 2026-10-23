# Owner dashboard redesign - 23 October 2026

## Delivered

- A phone-first owner workspace with Sales, Cash, Tank stock and Review navigation, a compact header and station workspace links. The long station sidebar is hidden only in the owner view; station entry screens retain their existing navigation.
- Owner login opens the owner dashboard. Other staff retain the organisation chooser.
- Combined fuel sales in rupees, separate petrol/diesel litres and station cards. Fuel revenue is before discounts; lubes, other income and net totals remain separately accessible.
- Same-weekday-last-week comparisons using matching fully recorded, priced shifts at each station. Missing/partial baseline data and zero baselines do not produce a fabricated percentage. Saved readings are labelled separately from daily closing approval.
- Clear empty, incomplete and unavailable-station states. Combined figures are withheld during a station outage. Missing cash opening accounts do not display a verified-looking zero balance.
- Recorded cash by station, with explicit distinction from physical counts and holder balances.
- Per-tank warning settings, defaulting to 5,000 L, editable in Tank administration. The station overview and owner dashboard use the same configured warning. Calculated stock, latest dip date and the difference at that dip remain distinct.
- Stock coverage from at least 3 complete reading days with positive consumption in the previous 7 days. Missing days are excluded, and a forecast below one day attracts attention. This does not represent an actual order or promised delivery.
- Incomplete-reading warnings after the 10:30 AM and 10:30 PM grace deadlines. Actual manager submission timestamps and late reasons are not inferred from reading creation time.
- Independent station summary protocol upgraded to schema 2, with validation of comparison and stock fields. Update both station services together.

## Still to implement from the broader brief

The redesign does not introduce cash-custodian accounts/transfers, recipient acknowledgement, owner confirmation on behalf, retained-change carry-forward, consolidated physical cash counts, new shift submission/correction locks, mandatory late/shortage explanations, automatic 10 PM business-date rollover, delivery ordering, or offline draft synchronisation. Existing daily close and ledger safeguards remain in use. These features require additional audited backend work; no working-looking controls were substituted for them.

The optional interface-language mechanism remains in place; new strings are marked for translation but this update does not establish a complete Hindi translation.

## Verification and local rollout

- Docker image built from repository source; Django system checks and migration consistency checks passed.
- 155 automated tests passed, covering comparison coverage, zero/missing baselines, empty days, cash readiness, grace deadlines, dip freshness, configurable warnings, sparse-history coverage, summary validation, currency grouping and owner/staff login routing alongside existing regressions.
- Browser review at 320 px and 390 px phone widths and the default desktop viewport, with no horizontal overflow at the tested phone widths. Navigation and second-station handoff checked using isolated synthetic databases.
- Encrypted backup verified before rollout, including both databases and recovery files; the secondary copy succeeded.
- Migration 0033 applied to both existing station volumes. Original column values, content digests and row counts across all 57 existing non-migration tables matched before and after in each station. SQLite integrity and foreign keys passed. No demo data was inserted into those volumes.
- Authenticated owner dashboard returned HTTP 200 with both live summaries; public login and stylesheet responses returned HTTP 200.

The screenshots under the workspace's `outputs/owner-redesign-*.jpg` use synthetic preview data. They are not operational reports and are not committed as business records. The separate hosted progress website is a deployment snapshot; updating its source in Git does not republish it.

Local entry: `http://127.0.0.1:8000/owner/`. The existing trusted-LAN installation remains a development prototype.
