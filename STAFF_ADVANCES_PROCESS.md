# Staff advances - 19 October 2026

1. In Staff advances record a payment already made: employee, cash/bank account, date, amount, reference and explanation. Bank reference is required. This records one outflow; it cannot transfer real money.
2. Record the monthly salary normally, with reviewed shortage deductions/adjustments.
3. In Clear an advance against salary choose the advance and that employee's saved salary. Enter a positive clearing amount, date and reason. It cannot exceed remaining advance or unpaid salary. Partial clearing across months is supported. Nothing is automatically cleared without this explicit link.
4. Check Advance cleared, Salary paid and Outstanding in Salaries & shortages. Outstanding = revised salary due - applied advances - active salary payments. Clearing an advance is not a second payment or expense.
5. Review/close the issue and clearing dates. Backdated entries through a closed period are locked. Owner-only corrections require reasons. Reverse linked clearings before reversing an erroneous advance record. Reversals correct records only; actual cash refunds/recovery are not implemented.

Duplicate request tokens are idempotent; reused tokens with different details are rejected. Bank/cash transaction references cannot be reused across active salary payments and advances in the same account. Cash entries cannot leave negative recorded balances. Employee mismatches, future dates, dates before account opening, excessive clearing, and salary adjustments below paid/applied amounts are rejected. Roles and admin prevent ordinary editing/deletion.

Both demo organisations: INR 1,000 advance from demo bank, fully cleared against October salary; INR 500 separately recorded salary payment; revised salary INR 11,960; outstanding INR 10,460. Hamara has one clearing; Shree Govind has two (400+600). No real money moved. Both days were reviewed and closed with prior synthetic quality/shortage exceptions acknowledged. Browser responsiveness was intermittent during the second demo; final state and financial totals were independently verified through application services and database integrity checks.

Validated with 122 passing automated tests, including cross-month partial clearing, duplicate tokens/references, money posted once, correction order, insufficient cash, employee mismatch, closed periods, roles, and adjusted salary protection. Migrations through 0030. Current prototype has no real banking API, actual advance repayment/refund workflow, automatic clearing policy, employee acknowledgement or payroll compliance certification.
