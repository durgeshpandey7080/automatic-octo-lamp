# Demo rehearsal - 19 October 2026

All existing Hamara Pump Narai records are demonstration data, confirmed by the owner. Shree Govind KSK now has a labelled DEMO day dated 18 October 2026. No real stock or balance is certified by these samples.

The demo includes eight nozzles, two shifts, 160 litres of fuel sales (80 petrol, 80 diesel), fuel sales of INR 15,200, two lube bottles sold for INR 100, credit and repayment, shift/station expenses, Paytm evidence matching, a bank settlement with fee, cash deposit, deliveries, quality observations and closing dips.

Verified: cash INR 15,820; bank INR 898; stock 1,020 litres in each tank; lube remaining 3 bottles; debtor balance zero; no closing exceptions. Owner self-review was recorded with a synthetic rehearsal reason. The day is CLOSED and a reading edit was rejected.

The sample entries remain visible in Shree Govind KSK. The reusable `demo_rehearsal --confirm-demo` management command refuses a station with existing tanks, shifts or money accounts and runs atomically. Do not use it on a real-data station. Samples do not certify production readiness.

## Salary shortage check - 19 October 2026

Shree Govind KSK now has a separate DEMO salary shortage employee and a sample shift on 19 October. Expected cash INR 7,600; submitted INR 7,500; shortage INR 100. October base salary INR 12,000; deduction INR 100; calculated salary due INR 11,900. Exactly one SalaryDeduction links the handover. Duplicate salary submission and replacement handover were rejected. This is a calculation, not a wage payment.

Additional temporary-database tests check that a previously deducted shortage is excluded from the next month and that saved handovers, salaries and deduction rows remain read-only in admin, including for the owner.

LIMITATION: no supported correction, refund or salary-adjustment workflow exists. An attempted corrected cash value cannot replace the saved handover. Therefore correction recalculation is NOT verified or implemented; an audited correction workflow is still needed. Do not bypass this by editing database rows directly.
