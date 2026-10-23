# Production roadmap

Planning date: 23 October 2026. This is an operations system for the owner's two pumps. It is not production ready. Milestones are evidence based, not calendar promises or a percentage inferred from test count.

## Confirmed deployment and business decisions

- New development on `dev`; reviewed promotion to `main` and a versioned release only after gates pass. VM installation uses that release, when access is supplied.
- Public HTTPS, without requiring a VPN. Five expected simultaneous users; assess correctness at ten concurrent users, including competing financial writes.
- All current local records are synthetic. Production starts with owner-approved opening stock, balances, cash custody, receivables/payables and staff setup; no demo financial history is imported.
- Shorter recovery than the proposed 15-minute data-loss / 4-hour restoration targets is required. Exact RPO/RTO and the redundancy budget are unresolved, so the recovery gate is blocked.
- Recipient disputes preserve the declared and actual amounts and require owner resolution. Never silently write off a difference, reduce a transfer or automatically deduct salary.
- Administrative SSH is reachable through the owner's OpenVPN network. Initial read-only VM audit: Ubuntu 24.04.5 LTS, 4 CPUs, about 8 GiB RAM and 61 GiB root disk; Docker and Compose available, clock synchronised, no running application containers. Public app HTTPS is still the intended end-user access; private administrative access does not provide public DNS/TLS automatically.
- Existing shift/closing, cash, stock and role decisions remain in `DESIGN_BRIEF.md`.

## Milestones and exit evidence

| Milestone | Scope | Current status | Exit evidence |
| --- | --- | --- | --- |
| M0 - Controlled development | `dev`, isolated synthetic lab, CI, main protection and baseline | G0 passed at code checkpoint 78bfa27 | Both-station rehearsals passed; 168 Django and 5 release-manifest tests passed; main PR/check rules and immutable version-tag rules active; hosted CI passed for code checkpoint 78bfa27 |
| M1 - Shift submission and business clock | Overnight date, 10 AM/10 PM close, grace, physical counts, reasons, submit/return/correct/approve | Partial: shared clock foundation; lifecycle pending | Boundary and late tests; lock all financial entry paths after submission; atomic snapshots; stale/concurrent approvals rejected; actor/reason history retained; closing can never approve an unfinished mandatory record silently |
| M2 - Cash custody and retained change | Per-pump drawer/manager/person balances, counted cash, next-shift change, acknowledgements, disputes | Planned | Every transfer conserves total cash; pending/disputed funds counted once; partial receipt and owner resolution tested; historical holder balances reproducible; no cross-pump leakage |
| M3 - Bank and payment reconciliation | Deposits/in-transit/confirmed bank, gross digital collections/net settlements/fees, refunds/reversals | Existing foundations; extensions pending | Duplicate references and retries; provider evidence vs bank evidence distinguished; failed/partial deposits; exact allocation; no cash/bank double count; original entries preserved |
| M4 - Operational completeness | Stock/dips/deliveries, customer credit/collections, suppliers, payroll/advances, exports, usable phone workflows | Existing foundations; gaps remain | Scenario matrix passes; agreed required vs optional features stated; measured vs calculated stock and its timestamp visible; reviewed opening data; immutable closing report and safe export checks |
| M5 - Production platform | Database choice, app server, environment/secrets, HTTPS/auth, off-VM recovery, logs/monitoring, deployment tooling | VM read-only preflight passed; architecture/recovery decisions unresolved | Deploy checks under actual production settings; ten-user contention/retry tests; access isolation; hardened public ingress; restore within agreed RPO/RTO; no development server or demo bootstrap |
| M6 - Staging acceptance | Exact release candidate, public-HTTPS staging, failure drills and owner/manager phone UAT | Not started | Synthetic end-to-end day plus fault cases; owner sign-off; no unresolved release blockers; staging uses production configuration and database engine with different secrets/data |
| M7 - Release and cutover | Reviewed `dev` to `main`, annotated tag, immutable image manifest, fresh verified openings, runbook and training | Not started | Release checklist accepted; tag/commit/image/schema recorded; rehearsed migration and rollback; no synthetic data or accounts; deployment from the same tested artifact |
| M8 - Controlled production pilot | One pump first, parallel paper record reconciliation, then second pump | Not started | Owner accepts matched closing reports and cash/stock/payment totals; recovery/monitoring working; rollout/rollback decision recorded |

## Gates that can stop a release

- **G0 - Source control:** main requires a PR and passing checks; released tags cannot be silently repointed. Branch protection is verified through GitHub, not assumed from this file. No direct development deployment to the current local installation.
- **G1 - Accounting correctness:** cash conservation, shift meter continuity, money precision/rounding, digital gross/fee/net allocation, custody disputes and reversal order pass independent expected-value tests. No automatic salary recovery from an unresolved shortage.
- **G2 - Integrity and concurrency:** migrations from a preserved baseline; ten-user writes with collisions and retries; exactly-once effects; no lost updates, double posting or cross-station access. SQLite compatibility is an open decision; current custom SQLite triggers must be ported/tested if the engine changes.
- **G3 - Public security:** production settings; supported WSGI/ASGI server; HTTPS, secure cookies, trusted hosts/proxies, CSRF, rate limiting, individual logins, owner MFA/recovery, holder-scoped permissions, dependency review, log redaction and secret rotation. Deliberate owner exception mechanisms cannot bypass mandatory integrity checks.
- **G4 - Recovery:** exact RPO/RTO agreed, separate failure-domain storage and keys, encrypted backups, measured restoration onto a fresh host, failure alerts, power-loss handling and a written paper fallback. Backup frequency alone does not prove recoverability.
- **G5 - User acceptance:** owner and manager can complete both shifts on a phone; explain shortage/late submission; dispute/acknowledge cash; reconcile deposit; review dip; return/correct/approve; export a closing report. New Hindi copy must be validated if Hindi is included in release scope.
- **G6 - Release reproducibility:** exact candidate commit, complete test report, production config preflight, dependency inventory, Docker image digest, migration version, rollback plan, release notes and owner acceptance. Any candidate code or configuration change invalidates affected evidence.
- **G7 - Cutover readiness:** VM/domain/TLS/storage reviewed, restored staging rehearsal passes, approved opening values reconcile, production credentials are fresh, intended ingress is verified, and monitoring/backup alerts reach the agreed operator. The first real owner close is a post-deployment M8 acceptance step, not a prerequisite that would make release tagging circular.

All gates are required for the initial public production release. A working page, a `--deploy` check, a large number of passing tests or a version tag alone cannot pass these gates. Evidence status is tracked in `RELEASE_GATES.json`.

Software completion precedes staging, but final production readiness also depends on the actual VM, HTTPS and restore drill. VM SSH was used only for inspection on 23 October; no software installation, service changes or deployment occurred. No separate Docker API is required for this host. DNS/backup-provider API access is optional if those services are to be configured automatically later.

## Risks the owner may not have encountered yet

- A browser timeout can mean a payment was saved but the response was lost. Safe retries need request identity and a way to check the prior result.
- Cash moves between people without creating revenue or expense. Pending acknowledgement, disputed short receipt and later bank deposit must preserve the money's history and originating pump.
- A UPI screenshot/provider success record is not the same as bank settlement. Fees, duplicates, refunds and batch settlements need separate handling.
- The calendar day and a 10 PM business-day boundary differ. Outstanding previous-day reviews must remain visible; DST/server timezone must not change Indian business dates.
- A tank difference may reflect timing, measurement or temperature. It is not automatically theft or employee liability.
- Approved corrections can affect later opening cash, meter continuity, stock and reports. Reopening one old day cannot silently restate all later approved days.
- A VM snapshot on the same disk can fail with the VM. Encryption keys and restore instructions need their own protected recovery copy.
- Source release tags and Docker tags are different. Tags can be moved; deploy the tested image by digest and record both identities.

## Technical references

- [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/): use actual production settings and a production server; keep debug disabled and production keys private.
- [Django SQLite limitations](https://docs.djangoproject.com/en/5.2/ref/databases/#sqlite-notes): database behavior and concurrent locking need measured validation; changing engines is not a configuration-only promise here.
- [Docker image digests](https://docs.docker.com/dhi/explore/security-concepts/digests/): record immutable image content identity in the release manifest.
