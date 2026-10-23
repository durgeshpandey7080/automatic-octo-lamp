# Owner dashboard implementation plan

Initial source inspection: 23 October 2026. This plan records the discovery checkpoint. See `REDESIGN_STATUS.md` for the first implemented dashboard and the backend features still outstanding.

## First phone screen

1. Station scope and business date, with last refresh and completeness clearly visible.
2. Combined fuel sales in rupees and petrol/diesel litres; compare matching submitted shifts with the same weekday last week.
3. Station cards stacked vertically, each showing sales, shift coverage and closing approval state.
4. Cash on hand, split by pump and holder, with latest counted cash and outstanding handovers available on expansion.
5. Per-tank book stock, dated physical dip, 5,000-litre warning threshold and estimated coverage when supported by enough history.
6. Review queue: overdue submissions, explained shortages, stock discrepancies and daily closes awaiting Durgesh.

Unavailable source data must be labelled unavailable; it must not be presented as zero or replaced with invented figures.

## Existing foundations and remaining work

| Area | Foundation seen in source | Work needed for the agreed design |
| --- | --- | --- |
| Owner summary | `pump/owner_dashboard.py` has authenticated summaries from separate station services, daily totals, completeness warnings and an owner-only view. | Separate fuel revenue from mixed net sales/income; add comparison coverage, shift timing, dip freshness and a mobile hierarchy. Extend and validate the peer-summary schema for any new fields. |
| Shift lifecycle | `Shift` has date, number and creation time. Daily close has its own submission/review fields. | Explicit shift submission lifecycle, locking/correction approvals, schedule, reliable submission times and late reasons. Creation time alone must not be treated as submission time. Preserve historical dates. |
| Cash | `Handover` records salesperson-to-manager receipts and variance. Money accounts and bank reconciliation already exist. | Map those receipts to manager custody without duplicate ledger entries. Add named-holder transfers, acknowledgements, owner confirmation on behalf, retained change and deposit confirmation states. Physical count and counted-at evidence must support the displayed balance. |
| Stock | `Tank` has capacity; stock summaries calculate book balance. `save_stock_entry` already restricts closing dips to Shift 2 with readings. | Per-tank warning configuration, dip/time presentation, coverage calculations and order/delivery context. Avoid representing a forecast as a confirmed delivery. |
| Permissions | Station roles and owner-only endpoints exist; the current role list has no dedicated cash-recipient role. | Verify manager station assignments and implement holder-scoped access across both stations without broadening recipient access to business records. |
| Connectivity | Entry JavaScript previews calculations locally. | Audit forms for draft retention, failed/unknown submission outcomes, server acknowledgement and safe retries. Calculation previews are not offline submission support. |

## Suggested implementation order

1. Define summary/data contracts and sketch the phone screen using existing verified fields. Clearly label data that needs backend work.
2. Implement business-date scheduling and shift submission/review with audited corrections and regression tests.
3. Implement custody, retained change, acknowledgements and deposits with ledger invariants and permission tests.
4. Implement stock threshold configuration, dip freshness and coverage estimation with missing-history handling.
5. Connect the phone dashboard to verified summaries; test both stations, incomplete days, unavailable peer service and narrow screens.

Keep current business data and existing financial history intact. Use isolated test databases and a staged rollout; a passing old test suite does not establish that these newly specified behaviors exist.
