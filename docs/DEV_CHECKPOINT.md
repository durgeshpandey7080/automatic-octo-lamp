# Development checkpoint - 23 October 2026

- Working branch: `dev`; release baseline on `main`: 59f40aafc10480fb5132a42c7529da551b93361b. No new main commit, release tag or production release created.
- Dedicated lab built using `compose.dev.yaml`; both empty synthetic station databases migrated and completed the integrated rehearsal. Owner summary across both services returned HTTP 200.
- Full development regression suite: **168 tests passed in 28.585 seconds**. Separate release-manifest validation: **5 tests passed**. Django checks and migration consistency passed.
- Lab mounts verified: only `pump_dev_dev_station1` and `pump_dev_dev_station2` data volumes. Private `.env.dev` is ignored by Git and excluded from image build context. No local station/recovery volumes are used by the lab. Existing local station image remains a separate image from the development build.
- GitHub main protection enabled for PRs and checks `verify`, `synthetic-lab (station1)` and `synthetic-lab (station2)`, with administrator enforcement, no force push/delete and conversation resolution. No independent approving review is required by GitHub on this single-owner repository; owner release acceptance remains an explicit process gate.
- Active ruleset `Immutable release tags` prevents update/deletion of future `refs/tags/v*`; no release tag exists.
- Initial VM SSH and Docker preflight passed through the owner's administrative network. VM resources were inspected only. No application was installed there. This does not establish security, public HTTPS, load capacity, backup durability or production readiness.

New code includes fail-closed synthetic seeding, production refusal of demo commands, isolated lab automation, shared Indian business-clock boundaries and release-manifest validation. Automatic business-date changes and audited shift submissions remain future application work.

Planning defaults: RPO at most 1 minute, RTO at most 30 minutes, a ₹2,000/month initial off-VM backup/monitoring allowance, Cloudflare DNS after the owner buys a domain, and paper shift records during outages with later owner-reviewed reconciliation. Owner MFA will use an authenticator app with saved recovery codes; staff will have individual accounts with access resets by the owner after identity verification. Backup retention and exact paper-form fields are deferred until the pilot. These decisions do not pass recovery or cutover gates; provider quotes, domain purchase, implementation and successful restore evidence remain outstanding. Audited shift/cash workflows, ten-user contention tests, actual production configuration, fresh-host recovery and owner UAT are also required. Only G0 has passed; G1 through G7 remain unpassed until their evidence is recorded.

Hosted CI first exposed a hardcoded restore UID assumption. Recovery now preserves the installed database owner and permissions; required ownership-change errors still fail recovery. The complete 168-test suite passes, and 9 backup/ownership tests also pass as UID/GID 1001. CI uses Ubuntu 24.04 and verified, pinned v6 action commits. Hosted CI passed all three jobs for code checkpoint 78bfa27; G0 is complete for this checkpoint.

Hosted CI evidence: https://github.com/durgeshpandey7080/automatic-octo-lamp/actions/runs/39977920913 . Future changes require their own CI results; this is not production acceptance.
