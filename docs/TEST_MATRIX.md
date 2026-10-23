# Synthetic acceptance matrix

Baseline: 155 tests passed at commit 59f40aa. Current local development checkpoint: 168 Django tests, 5 release-manifest tests and both synthetic station rehearsals passed. This matrix is coverage planning, not a claim that every scenario below passes.

| Area | Required cases | Evidence/status |
| --- | --- | --- |
| Lab boundary | Explicit flag/environment/name/confirmation; empty-only; production refusal; repeat refusal; atomic rollback; no existing-user reuse | New automated tests and CI lab |
| Shift and time | Overnight business date; 10 AM/10 PM; half-hour grace; leap/year rollover; server UTC; missing/late submission; active draft preserved | Clock foundation implemented; audited submission and draft tests pending |
| Meter entry | All eight nozzles; continuity; non-decreasing readings; duplicates; invalid prices; returned testing; transaction rollback | Existing regressions; add concurrent submissions and lost-response retries |
| Cash and custody | Counted vs expected; retained change; holder transfer; cross-pump balances; partial receipt; dispute/resolve; duplicate request/reference; acknowledgement/on-behalf actor | New custody implementation and tests pending |
| Money and payments | Cash/bank conservation; pending deposit; gross/net/fee; partial/failed deposit; settlement batches; duplicate imports; refunds; reversals; closed dates | Existing ledger/import regressions; pending workflow extensions |
| Stock | Opening, purchase/delivery, two shifts, returned test, dip vs saved expected, low threshold, sparse history, absent/late delivery | Existing stock/owner regressions; ordering and calibration scope unresolved |
| Accounts/payroll | Credit sale/recovery, partial supplier payments/credits, salary/advance/shortage correction and reversal order | Existing regressions; verify production scope and reports with owner |
| Roles | Manager assigned station; owner both; cash recipient own records only; disabled account; endpoint/direct-object access; no shared account | Existing role regressions; holder role and production login hardening pending |
| Closing/correction | Missing mandatory records; shortage explanations; immutable submitted snapshot; stale/double approval; return/correct/reapprove; later-period propagation | Existing daily-close regressions; new shift lifecycle pending |
| Browser/device | 320/390 px; long names/amounts; validation preserves input; connection failure/unknown result; duplicate tap; print/export; Hindi if in scope | Baseline owner layout checked; complete workflow UAT pending |
| Failure/concurrency | Ten users with competing writes; crashed request; station service down; disk full; DB locked; VM restart; clock skew; timeout after commit | No production-scale evidence yet; release blockers |
| Restore/cutover | Fresh database migrations; reviewed openings; encrypted off-VM restore/key recovery; exact image rollback with DB compatibility | Local backup checks exist; future-host drill and accepted RPO/RTO pending |

Every new accounting behavior needs independently calculated expected totals and rejected-action assertions proving no financial writes occurred. Do not replace a failed test with a broader exception or invented fixture result just to get a green build.
