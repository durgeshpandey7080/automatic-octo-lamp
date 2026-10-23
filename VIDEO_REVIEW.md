# Petrometer cashier demo: useful workflows

Reference: https://www.youtube.com/watch?v=bIPr-7AVjKw
Title: How to assign duty to cashier-Demo in hindi (Petrometer), duration 9:26.
Reviewed the exported auto-generated Hindi transcript and sampled the screens at
about 2:01, 3:46, 4:43, 6:36 and 8:29. Transcript captions have gaps; this is not
an assertion that every frame or every feature was fully reviewed.

| Demo section | Useful idea | Pandey Petrol Pump status |
|---|---|---|
| 0:14-1:56: login, cashier/gun selection, opening readings | Staff responsibility and multiple nozzle assignments | Existing reading entry assigns each of eight nozzles. Added Shift workspace connecting the saved shift to each salesperson. Separate start-duty/open-shift drafts remain future work. |
| 2:07-2:59: closing readings, sold quantity, testing | Calculate sales and separately track non-sale dispensed fuel | Existing closing minus opening and saved rate calculation. Testing fuel is not implemented; requires returned-to-tank vs consumed handling before changing revenue/stock. |
| 3:09-3:46: lube product, quantity, price, discount, tax, payment | Keep product sales separate and make totals clear | Existing named products, units, saved sale rates and assigned shift; workspace links directly to the right person. Purchase/stock ledger, discounts, taxes and invoicing remain future work. |
| 3:55-4:43: credit slips | Customer, vehicle, fuel/product, quantity and rate together | Existing debtor accounts, unique reference, credit allocations and repayments. Vehicle/product/quantity slip details are future work; credit must not add nozzle sales twice. |
| 5:00-6:36: other income and expenses | Separate incidental income from fuel and classify payment sources | Existing expense vouchers and source split. Other income and split-source expense vouchers are future work. |
| 6:50-8:49: cash, wallet, POS, manager receipt | Compare cash/digital collections against sales and show shortage/excess | Existing cash, Paytm Business, PhonePe Business, card, manager receipts and shortage. Workspace displays settlement status and linked records. Individual wallet/POS transactions and bank reconciliation remain future work. |
| 8:57 onward: end duty | Review before final settlement | Existing saved handover is immutable and locks linked entries. Workspace makes that lock explicit and provides the day's closing report. |

## Changes delivered from this review

- New Shift workspace: readings -> shift details -> collections -> daily review.
- Salesperson cards with separate petrol/diesel litres, lube sales and gross sales.
- Lube/credit/expense actions prefill the selected shift and salesperson.
- Saved handovers show receiving manager, cash submitted and shortage/excess.
- Entry links disappear after handover; historical receipts stay view-only.
- Existing organisation isolation is retained.

## Remaining work in recommended order

1. Open-duty drafts and explicit cashier/nozzle assignments before closing.
2. Testing fuel quantities with return/disposal classification and audited corrections.
3. Detailed customer credit slips with vehicle, product, quantity and rate.
4. Other-income vouchers and transaction-level wallet/POS references.
5. Lube purchases, inventory and stock warnings.
6. Cash float/office receipts/returns, bank reconciliation and correction audit trail.
7. Discounts, taxes and invoices only after the applicable business rules are specified.

Do not copy demo amounts into real records, allow silent edits to historical
openings, or delete settled payment entries without a correction/audit workflow.
This file is a comparison and implementation backlog, not a claim that the
remaining features have been built.

## Implementation update - 19 October 2026

Items 1-6 now have working local workflows: duty drafts, returned testing and
reversals, detailed credit slips, other-income/digital records, lube inventory,
and cash transfers/bank matches/audit. Item 7 provides auto-numbered ordinary
sales receipts; tax/discount calculations remain disabled by explicit user
instruction. See OPERATIONS_GUIDE.md for scope, operating order and limits.
