# Shortage recovery — 20 October 2026

Open Shortage recovery in the sidebar. Owner chooses original handover, receiving cash/bank account, open receipt date, amount, transaction reference and explanation. Receipt numbers are automatic. Record money already returned; the software does not collect or transfer money.

Before saved payroll: active receipts reduce the pending shortage. After saved payroll: active linked receipts add salary credit exactly once. Original handover, deduction and waiver history remain unchanged. Waived amounts are not recoverable here. Cash/bank receives one positive movement, separate from sales and expenses. Daily report lists recovered money separately.

Corrections preserve receipt and audit history. Erroneous receipts may be reversed on an open date, unless this would leave salary overpaid or cash negative. A pre-payroll receipt cannot be reversed here after payroll exists: reviewed payroll correction is still future work. Actual refunds are not implemented. Closed original shifts can receive a later dated recovery without reopening the shift; closed receipt dates stay locked.

Verification: 127 automated tests passed, including five recovery tests covering before/after payroll, full/partial receipt, waiver limits, duplicate token/payload/reference, cash/bank, invalid amounts, roles, future dates, closed periods and correction constraints. Both stations migrated through 0032.

Chrome demo in both organisations on 20 October: receipt 40 against original shortage 100 with waiver 60. Salary revised due 12000, advances cleared 1100, paid 500, outstanding 10400. Hamara cash 15340; Govind cash 15840. Demo only; no real money moved. 19 October stays closed and 20 October open.

This remains a local prototype, not production-ready.
