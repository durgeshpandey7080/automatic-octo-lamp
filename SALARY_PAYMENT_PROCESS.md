# Salary payment process - 19 October 2026

1. Record the fixed monthly salary and review shortages.
2. Approve a reasoned deduction adjustment if needed; original records stay intact.
3. Make the actual payment outside this software.
4. In Salaries & shortages choose Record payment. Select the actual cash/bank account, payment date, amount, external reference (required for bank) and explanation. Partial payments are supported.
5. Check revised due, paid and outstanding amounts and the cash/bank statement. Do not duplicate the payment as an expense or transfer.
6. Submit/review/close the payment date. Closed periods require reasoned owner reopening for corrections.

Owner-only payment recording/reversal, automatic SALPAY references, duplicate request protection, per-account external-reference checks, outstanding-balance caps and cash availability checks are implemented. Payment corrections retain the original reversed record and actor/reason in the audit log. Salary adjustments cannot reduce salary due below recorded payments. Cash/bank outflows are included once; daily reports list salary payments separately from sales and expenses.

Both demo organisations now show revised salary INR 11,960, paid INR 500, outstanding INR 11,460. Hamara has one active cash payment. Shree Govind has a reversed cash payment and one active bank replacement. Both demo days were reviewed and closed again with their pre-existing explicit quality/shortage exceptions retained. No actual money was paid.

116 automated tests passed. Chrome verified overpayment rejection, closed-date rejection, partial payment, reversal, replacement and updated balances. Both station databases migrated through 0028.

This records money already paid; it cannot send money or verify bank execution. Salary advances, actual cash recovery/refunds, employee acknowledgement, pay-slip export and a full payroll compliance workflow are not implemented. Bank overdrafts remain possible; station cash is checked for negative recorded balances. This is a local prototype, not production ready.
