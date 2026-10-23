window.REPORT = {
  "title": "Pandey Petrol Pump — Project Report",
  "snapshotDate": "23 Oct 2026",
  "tests": 168,
  "triggersPerStation": 96,
  "migration": "0033",
  "verification": [
    "Closed-day transitions, stale reviews and reasoned owner exceptions",
    "SQLite bulk-update, deletion and backdated-entry locks",
    "Cash transfers, net bank settlements and no double expense deduction",
    "CSV preview, confirmation, duplicates and exact evidence matching",
    "Historical debtor ageing, quality observations and station access",
    "Encrypted backup recovery, corruption checks and secondary-copy recovery",
    "Integrated two-shift rehearsal and owner-only setup readiness checks",
    "Salary adjustment/undo/stale form protection, approved discounts and bulk allocations without duplicate sales",
    "Fresh Chrome workflows in both stations, closed-date rejection, and independent financial/database invariants across all 50 model sections",
    "Salary partial payments, reversals, bank/cash posting once, outstanding caps and paid-salary adjustment protection",
    "Staff advances, partial salary clearing, reversals, duplicate references and paid-salary caps",
    "Shortage receipt before/after payroll, waiver limits, retries, correction limits, cash/bank posting and closed dates",
    "Combined owner summary: both service directions, owner-only access, expiring signed requests, date/settlement cutoffs, missing-service handling and no ledger writes",
    "Local AI: allowed check IDs only, no free-form factual claims, owner-only access, no cloud fallback, isolated container, timeout/concurrency, input minimisation and escaped output",
    "Owner phone redesign: matching-shift weekly comparisons, missing/zero baselines, sparse stock history, configurable thresholds, dip freshness, reading grace deadlines and login routing",
    "Dev-only isolation: both synthetic stations reconciled; 166 Django regressions and 5 release-manifest checks passed; main/tag protections configured",
    "CI-discovered restore ownership assumption fixed; 168 full regressions and 9 backup/ownership tests under UID/GID 1001 pass locally"
  ],
  "roadmap": [
    {
      "id": "backups",
      "priority": 1,
      "title": "Backups & tested recovery",
      "status": "implemented",
      "summary": "Encrypted hourly bundles, two protected folders and restore rehearsals.",
      "built": [
        "Both station databases, source, private settings and persistent uploads",
        "Decryption, checksums, integrity, foreign keys and record-count verification",
        "Owner-only status page and manual backup requests",
        "PowerShell verify-only rehearsal and guarded restore procedure"
      ],
      "remaining": "Both copies are on this PC. A disconnected external copy and separate protected recovery key are still needed for disk-loss protection."
    },
    {
      "id": "closing",
      "priority": 2,
      "title": "Manager-approved daily closing",
      "status": "implemented",
      "summary": "Submit, review, close and reopen with an audit trail.",
      "built": [
        "Saved review fingerprint and summary snapshot",
        "Changed records require a fresh submission and review",
        "Unresolved cash, stock and quality exceptions remain visible",
        "Owner-only reasoned reopening; SQLite guards protect dated records"
      ],
      "remaining": "No live day has been closed for demonstration. Use actual complete records; owner exception approval does not erase a discrepancy."
    },
    {
      "id": "cash-bank",
      "priority": 3,
      "title": "Cash & bank controls",
      "status": "implemented",
      "summary": "Actual money movements, account assignments and one-time transfers.",
      "built": [
        "One pooled station-cash account and multiple bank accounts",
        "Opening balances, cash deposits, withdrawals and bank transfers",
        "Net bank settlements and explicit assignment of existing bank movements",
        "CSV statements; owner corrections and reversals retain history"
      ],
      "remaining": "Enter actual opening balances and assign bank movements. This is a cash/bank subledger, not a full general ledger; owner-capital journals are not yet included."
    },
    {
      "id": "digital",
      "priority": 4,
      "title": "Paytm / PhonePe reconciliation",
      "status": "partial",
      "summary": "Normalized evidence imports with preview and duplicate checks.",
      "built": [
        "Two-step UTF-8 CSV preview and confirmation",
        "Provider/merchant/reference duplicate protection",
        "Exact matching against existing digital collections",
        "Imported evidence creates no extra sales, collections or bank credits"
      ],
      "remaining": "Native provider exports have not been verified against your files. Live APIs, bank-statement imports, refunds and many-to-one settlement allocation remain future work."
    },
    {
      "id": "debtors",
      "priority": 5,
      "title": "Debtor recovery & ageing",
      "status": "partial",
      "summary": "Customer accounts, repayments, statements and unpaid-age buckets.",
      "built": [
        "Separate customer ledgers with opening balances and repayments",
        "Credit slips with product, vehicle and saved-rate details",
        "As-of-date ageing with oldest-first reporting allocation",
        "Print and CSV export, including inactive accounts with balances"
      ],
      "remaining": "Credit limits, payment terms and saved bill-by-bill repayment allocation remain unimplemented. Age buckets are not contractual overdue classifications."
    },
    {
      "id": "quality",
      "priority": 6,
      "title": "Tank stock & quality records",
      "status": "partial",
      "summary": "Deliveries, stock/dip comparison, density and water observations.",
      "built": [
        "Actual tank openings, deliveries and closing physical dips",
        "Morning and after-delivery density/temperature observations",
        "Optional verified density at 15°C with correction reference",
        "Water checks, reversal history and closing-exception checks"
      ],
      "remaining": "No automatic temperature correction or quality certification. Tanker compartment/seal records, calibrated dip-chart conversion and a complete delivery inspection checklist remain future work."
    },
    {
      "id": "permissions",
      "priority": 7,
      "title": "Staff roles & owner controls",
      "status": "implemented",
      "summary": "Local station roles with endpoint restrictions and audited assignments.",
      "built": [
        "Cashier, Manager, Accountant, Viewer and disabled station access",
        "Owner-only staff assignments, backup controls and reopening",
        "Existing superadmin access to both separate organisations",
        "Restrictions apply to direct requests, not only menu links"
      ],
      "remaining": "The owner must deliberately assign roles to staff logins. Legacy accounts retain previous behaviour until reviewed. Cashier reads are station-wide, not salesperson-only."
    },
    {
      "id": "payroll",
      "priority": 8,
      "title": "Salary payments & advances",
      "status": "partial",
      "summary": "Salary due, payments, advances and shortage recovery with separate money movements and audit history.",
      "built": [
        "Fixed monthly salary calculation",
        "Existing shortage deduction links avoid repeated deduction",
        "Separate staff salary records",
        "Owner-only shortage waiver/restoration history, with original records preserved and duplicate/stale submission protection",
        "Owner-only partial salary payments and outstanding balance tracking",
        "Cash/bank ledger integration, reasoned payment reversal and duplicate/overpayment/closed-date protection",
        "Staff advances paid from cash/bank, partial clearing across salary records and reasoned corrections",
        "Shortage money receipts, automatic linked salary credit and protection against collecting waived or recovered amounts twice"
      ],
      "remaining": "Actual salary refunds, employee acknowledgement and complete payroll compliance remain future work. Reversing a pre-payroll receipt after payroll is saved is blocked pending a reviewed payroll correction. Entries record money; they do not transfer or independently verify it."
    },
    {
      "id": "owner-view",
      "priority": 9,
      "title": "Combined owner dashboard",
      "status": "implemented",
      "summary": "Phone-first owner dashboard with fuel sales, matching-shift weekly comparisons, recorded cash, tank warnings and a review queue.",
      "built": [
        "Date-filtered net sales plus other income, separate petrol/diesel litres and lube totals",
        "Recorded cash/bank, customer and supplier balances, estimated debt older than 30 days, pending digital settlements and unallocated bank movements",
        "Shortage balance after waivers/returns, stock balances, day completion/closing status and station drill-through",
        "Owner-only expiring signed service summaries, visible timestamps, bounded timeouts and withheld combined totals when a station is unavailable",
        "Optional local Qwen3/Ollama ranks verified owner checks in English/Hindi, with source figures retained and no financial tools",
        "Owner-first login and phone navigation; configurable tank warning levels, dated physical dips and coverage from complete reading days"
      ],
      "remaining": "Cash custody/recipient acknowledgements, physical cash counts, retained-change carry-forward, audited shift submissions/corrections, mandatory late reasons, 10 PM business-date rollover and offline synchronisation remain planned. Cash is recorded ledger balance, not physical verification."
    },
    {
      "id": "exports",
      "priority": 10,
      "title": "Accountant exports & margins",
      "status": "partial",
      "summary": "Operational reports and CSV exports, with profit calculations deferred.",
      "built": [
        "Daily closing print report",
        "Cash/bank statements and debtor-ageing CSV exports",
        "Supplier purchase costs, credits and outstanding balances",
        "Automatically generated internal document numbers",
        "Daily workbench with two shift status cards and money allocation check",
        "Owner-approved shift discounts and nozzle bulk-sale allocations without duplicate stock or revenue"
      ],
      "remaining": "Full double-entry accounting, validated Tally-compatible exports, inventory valuation and trustworthy profit/margin reporting remain future work. Tax stays disabled. Flat-rupee shift discounts are enabled; item receipt allocation is not supported."
    }
  ],
  "history": [
    {
      "phase": "01 · FOUNDATION",
      "icon": "▤",
      "title": "The first working pump system",
      "body": "Django project, Docker setup, tank/nozzle models, migrations, validation, admin, tests and beginner instructions."
    },
    {
      "phase": "02 · DAILY WORK",
      "icon": "⇄",
      "title": "Eight nozzles, two shifts",
      "body": "Opening and closing litre readings, date-specific saved rates, salesperson assignments and meter continuity. Rupee-meter inputs removed."
    },
    {
      "phase": "03 · COLLECTIONS & ACCOUNTS",
      "icon": "₹",
      "title": "Money and customer records",
      "body": "Manager cash handovers, Paytm/PhonePe splits, separate expenses, debtor accounts, lube records and monthly salary calculations."
    },
    {
      "phase": "04 · TWO ORGANISATIONS",
      "icon": "◈",
      "title": "One software, separate stations",
      "body": "Hamara Pump Narai and Shree Govind KSK, shared owner sign-in, organisation switching, superadmin access and station company logos."
    },
    {
      "phase": "05 · STOCK & OPERATIONS",
      "icon": "▱",
      "title": "From delivery to reconciliation",
      "body": "Tank stock/dips, returned testing fuel, duty drafts, supplier purchases/payments, digital settlement records, receipts and reasoned reversals."
    },
    {
      "phase": "19 OCT 2026 · CURRENT CHECKPOINT",
      "icon": "✓",
      "title": "Backups, controls and reporting",
      "body": "Encrypted recovery copies, daily approval/locks, assigned roles, cash/bank subledger, payment evidence imports, debtor ageing, quality observations and 112 passing tests."
    },
    {
      "phase": "19 OCT 2026 · ISOLATED PILOT",
      "icon": "✓",
      "title": "Full daily workflow rehearsed",
      "body": "An isolated synthetic pilot verified the full daily workflow. The owner subsequently confirmed both installations contain demo data and authorised visible sample entries in Shree Govind KSK."
    },
    {
      "phase": "19 OCT 2026 · CORRECTIONS & SECOND VIDEO",
      "icon": "✓",
      "title": "Salary adjustments, discounts and daily workbench",
      "body": "Owner-only salary adjustment history, flat-rupee shift discounts with tax disabled, two-shift daily workbench, explicit money allocation and nozzle bulk allocations. Direct tank bulk withdrawals, customer bill-level repayment allocation and actual payroll payments remain future work."
    },
    {
      "phase": "19 OCT 2026 · EVERY-SECTION CHROME DEMO",
      "icon": "✓",
      "title": "Both stations tested through fresh two-shift workflows",
      "body": "After the requested reset, Chrome samples now cover stock, deliveries, quality, lubes, debtor credit/repayment, expenses, suppliers, digital/cash/bank records, receipts, bulk allocation, discounts, salary adjustments, disabled roles and owner-reviewed closing. All 50 pump models contain records per station; 112 automated tests pass. CSV browser upload was blocked by extension permission, so synthetic import/matching used the application service and was inspected in Chrome. Quality/shortage exceptions and two pending digital settlements per station remain visible. No real money moved."
    },
    {
      "phase": "19 OCT 2026 · SALARY PAYMENT PROCESS",
      "icon": "✓",
      "title": "Track salary due, payments and remaining balance",
      "body": "Owner-only cash/bank salary payment records, partial payments, correction history, duplicate protection and closed-date locks. Chrome demos in both stations show 500 paid and 11,460 outstanding; one erroneous cash record was reversed and replaced by a bank record in Shree Govind KSK. Both demo days are closed again. No actual money moved. 116 tests pass."
    },
    {
      "phase": "20 OCT 2026 · ADVANCES & SHORTAGE RECOVERY",
      "icon": "✓",
      "title": "Prevent collecting the same staff balance twice",
      "body": "Both stations now include advances, salary clearing and actual shortage receipt records. Visible Chrome demo: each has advances cleared 1,100, salary paid 500, waiver 60 and shortage recovery 40; salary outstanding is 10,400. Original closed 19 Oct handovers remain unchanged; 20 Oct receipts remain open. No real money moved. 127 tests pass; migration 0032."
    },
    {
      "phase": "20 OCT 2026 · COMBINED OWNER DASHBOARD",
      "icon": "✓",
      "title": "Both organisations in one read-only view",
      "body": "Chrome verified the dashboard from both station services. Completed demo day 19 Oct shows combined net sales plus other income 31,200, petrol 158 L, diesel 160 L, lube 1,000 and four pending digital collections totalling 400. The 20 Oct view includes the staff advances and recovered shortage: cash 31,180, bank 195,896 and shortage balance zero. Separate databases remain intact. 138 tests pass; no schema change beyond 0032."
    },
    {
      "phase": "22 OCT 2026 · LOCAL AI",
      "icon": "✓",
      "title": "On-PC priorities from verified checks",
      "body": "Local CPU model installed, cloud features disabled, internal-only network and no published AI port. The first free-form narration made factual mistakes and was rejected. The final workflow lets AI rank only validated check IDs; all factual text and amounts come from application rules. English/Hindi and current/both-station scope are supported. No cloud fallback or financial record changes. 146 tests pass."
    },
    {
      "phase": "23 OCT 2026 - OWNER REDESIGN",
      "icon": "+",
      "title": "Sales-first dashboard for the owner phone",
      "body": "Phone-first layout, matching-shift same-weekday comparisons, dated dips, per-tank warnings and recorded cash. 155 tests pass. Both station databases migrated to 0033 with all original records unchanged. Custody and shift-submission extensions remain planned."
    },
    {
      "phase": "23 OCT 2026 - CONTROLLED DEVELOPMENT",
      "icon": "+",
      "title": "Dev branch, synthetic lab and production gates",
      "body": "New work stays on dev. Isolated two-station rehearsal passes; main requires PR/checks and version tags cannot be moved/deleted. Production gates cover shift/cash workflows, ten-user contention, public HTTPS, recovery and release reproducibility. Initial VM read-only preflight passed; no deployment or production release."
    }
  ],
  "setup": [
    "Confirm actual tank capacities, nozzle mappings and equipment names; replace demo configuration.",
    "Enter real tank/lube stock and start-of-date cash/bank opening balances.",
    "Assign each staff login its intended role in the correct organisation.",
    "Record actual measurements and review daily exceptions before closing.",
    "Map a copy of your successful Paytm/PhonePe report to the supplied CSV headings.",
    "Keep an external encrypted backup copy and a separately protected recovery key.",
    "Pilot one station against existing registers before relying on the software."
  ],
  "next": [
    "Implement audited shift submission/correction and physical cash counts.",
    "Implement per-pump custody, acknowledgements and owner resolution of disputes.",
    "Planning defaults adopted: RPO \u003c=1 minute, RTO \u003c=30 minutes, \u003c= INR 2,000/month initial off-VM backup/monitoring allowance, Cloudflare DNS on an owner-controlled domain, and paper fallback; prove recovery and obtain provider quotes.",
    "Prove database correctness at ten concurrent users and complete public-HTTPS hardening.",
    "Run staging UAT and fresh-host restore, then review main promotion and release artifact.",
    "Add employee payment acknowledgement and reviewed salary refunds.",
    "Verify your actual provider export formats and add native report adapters.",
    "Add bank-statement matching, refunds and settlement-batch allocation.",
    "Add customer credit limits, payment terms and bill-level allocations.",
    "Extend delivery inspection and approved tank calibration records.",
    "Harden deployment, rehearse full PC-loss recovery and run a controlled pilot."
  ]
};
