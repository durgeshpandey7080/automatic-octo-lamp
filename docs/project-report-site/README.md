# Private project report site

This is a standalone owner-private Sites website, separate from the Django pump software. It contains project progress only: no customer records, balances, login credentials, backup keys or source from the business application.

Canonical progress content: `report-data.json`. Presentation: `dist/index.html`, `dist/style.css`, `dist/app.js`. Run `node build.mjs` after changing content to refresh `dist/report-data.js` and validate the roadmap. No dependency installation or framework build is required.

When project development changes, update statuses, test counts, scope, history and limitations from actual verified evidence, then republish this existing private Site. Preserve `.openai/hosting.json`'s project identity and owner-only access. Use the Sites skill and source workflow helper; never register a replacement Site or store source-write credentials in files.

This is a published snapshot. It has no live access to the PC or operational databases and no unattended update schedule. Future development checkpoints need a content update and redeployment. Do not imply that a planned or partial feature is complete, or that software tests establish regulatory compliance or production readiness.

The development history is summarized in phases where exact completion timestamps were not recorded. Current verification: 102 tests passed, migrations through 0022 on both station databases, 78 date-lock triggers per station. Existing business records were retained and no sample financial records were inserted.
