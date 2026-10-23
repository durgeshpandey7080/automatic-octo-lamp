# Development and synthetic testing

All new work goes to `dev`. `main` is frozen at the existing local prototype until a reviewed promotion passes the release gates. Existing history is preserved; creating `dev` does not delete or rewrite `main`. Do not copy development changes into `outputs/hpcl_pump`, retag the live `hpcl_pump-web` image, or start its Compose project during development.

## Isolated Windows lab

Use PowerShell in this repository:

```powershell
.\scripts\dev-lab.ps1 Init
.\scripts\dev-lab.ps1 Build
.\scripts\dev-lab.ps1 Seed
.\scripts\dev-lab.ps1 Start
.\scripts\dev-lab.ps1 Verify
```

This uses the standalone `compose.dev.yaml`, project `pump_dev`, image `pump-dev-lab:local`, its own station volumes, and loopback port 8015. No local station, backup or recovery volumes are mounted. The private signing key and optional synthetic-owner login password live in ignored `.env.dev`, which is also excluded from Docker build context.

`Seed` applies migrations and rehearses both synthetic stations using the application services. It refuses a nonempty station or existing user table and never resets it. If seeding one station succeeds and the other fails, investigate that station rather than rerunning or deleting both volumes. Stop with `.\scripts\dev-lab.ps1 Stop`; volumes remain available for investigation.

The lab validates a labelled two-shift day: 160 L fuel, Rs 15,200 fuel sales, Rs 100 lubes, recorded cash Rs 15,820, bank Rs 898, both tanks 1,020 L, cleared synthetic debtor and an approved locked closing. Those amounts are synthetic assertions, not business openings. The full regression suite exercises additional failure cases; this rehearsal alone does not cover all production behavior.

The synthetic entry command requires development/test mode, an explicit enable flag, confirmation, and a database named `synthetic.sqlite3` (or an isolated in-memory test database). Production mode refuses all demo commands. These are additional guards, not a substitute for keeping development and production storage and credentials separate.

## Promotion discipline

Commit and push to `dev`; require passing CI and evidence for the milestones in `ROADMAP.md`. Review through a PR into `main`. No automatic merge, production tag or VM deployment occurs merely because tests pass. When the owner accepts the completed release and all gates pass, promote the reviewed commit, create an annotated version tag, and record the tested image digest. Never move or reuse a released tag.

Production will start with approved real opening balances; the owner confirmed all current local data is synthetic. Keep that historical demo installation intact until production cutover is accepted. Do not import its demo users, transactions or signing/recovery keys into production.

VM access will be supplied later. Until then, infrastructure validation and production deployment are pending; passing local containers is not evidence that the future VM meets the gates.

Current planning defaults are RPO at most 1 minute and RTO at most 30 minutes, with an initial allowance of ₹2,000/month for off-VM backups and monitoring. Use Cloudflare DNS for an owner-controlled domain unless the owner selects another provider. During outages, staff use the shift paper record and reconcile it after recovery with owner review; full offline sync is deferred. These are planning choices, not proof that the VM or a provider can meet the recovery targets. Confirm quotes and select the domain before configuring public HTTPS.

## Release manifest preflight

`python scripts/check_release.py` intentionally fails for the current gate register. Before a production release, prepare a separate accepted manifest for the exact candidate commit and run `python scripts/check_release.py --manifest PATH`. A separate manifest avoids the impossible cycle of committing a file containing its own commit hash. Store the accepted manifest with release artifacts. The script checks required gate evidence references, owner acceptance, version, digest and recovery targets; it does not authenticate external evidence or make an unsafe deployment safe. It never creates a tag or deploys.

GitHub protection was configured on 23 October: `main` requires PRs, current CI (regressions and both synthetic station jobs), conversation resolution and applies to administrators. It forbids force pushes and deletion. Approving-review count is zero because this is currently a single-owner repository; explicit owner release acceptance remains required in the release process. The active `Immutable release tags` ruleset forbids update/deletion of `refs/tags/v*` without bypass actors. No version tag has been created.
