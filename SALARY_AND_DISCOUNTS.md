# Salary adjustments, discounts and daily workbench

Tax is disabled. Discounts are enabled, as requested on 19 October 2026.

## Salary shortage adjustments
Open Salaries & shortages, then Adjust deduction on a linked shortage (owner only). Enter the revised shortage amount and an explanation of at least 10 characters. Revised amounts must be between zero and the original deduction. An adjustment credits or restores the difference in salary due. Original salary, deduction and handover records remain unchanged. History shows the owner, timestamp, old/new deduction and reason. The database rejects adjustment updates/deletions and invalid adjustment chains. Duplicate submission tokens cannot create an extra credit; stale forms are rejected.

This is a salary-due adjustment, not a cash receipt, refund payment, salary payment or correction of the cash ledger. If actual cash is subsequently received, it needs a separate supported cash-recovery workflow, which is not implemented. A historical daily close is not rewritten. Pending shortages without a saved salary cannot be adjusted using this screen.

Demo in Shree Govind KSK: original INR 100 deduction on INR 12,000 salary; full waiver, reversal of that waiver, then partial waiver leaving INR 40 deduction. Original net INR 11,900; adjustment credit INR 60; revised due INR 11,960. Original cash shortage remains INR 100.

## Discounts
In Shift workspace, before handover, choose Approve discount (owner only). Enter a flat rupee amount and reason. Discount cannot exceed available fuel/lube sales or leave existing credit/digital allocations above net sales. Duplicate submissions are idempotent. Reverse an incorrect discount from its history with a reason before handover/closed date. To correct an amount, reverse it and add a replacement. Gross fuel/lube amounts, saved rates, litres and stock remain unchanged. Net salesperson dues, handovers, daily reports, dashboard amounts and revenue chart include the discount once. Item sales receipts remain at gross saved rates: shift discounts are disclosed separately in the day report, not allocated to individual item receipts. Percentage/item-level discounts are not implemented.

## Daily workbench
The sidebar Daily workbench opens a date, two shift status cards, links to each saved shift, and the allocation check. Positive remainder means shortage; negative means excess. Missing handovers are not assumed to be received money. Supplier payments, bank settlements and deposits remain separate ledger movements.

## Nozzle bulk allocations
The Bulk allocations sidebar records a customer, vehicle and litres already inside a saved nozzle reading. Auto references are generated. Records cannot exceed that nozzle's sold litres and add no second financial or stock posting. Separate actual debtor/collection entries still use their normal screens. Direct tank withdrawals are excluded.

Validation: 112 automated tests passed, including duplicate and next-month salary protection, adjustment/undo/stale/bounds/permissions, append-only guards, discount net handover and reversal/close locks, and bulk allocation no-double-count checks. Both stations migrated through 0026. Both are demo installations per the owner; not production ready.
