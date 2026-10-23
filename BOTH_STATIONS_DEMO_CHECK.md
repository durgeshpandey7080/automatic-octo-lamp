# Both-organisation demo coverage - 19 October 2026

The owner confirmed that existing records are demo data and requested sample entries in every section in both organisations.

## Verified results

- Full automated suite: 112 tests passed.
- Both databases: integrity OK; zero foreign-key violations.
- 23 owner pages per organisation returned HTTP 200.
- All 50 pump models have records in each organisation.
- Four demo role profiles per organisation have unusable passwords (password login disabled). Owner-only backup/access/admin restrictions returned HTTP 403 for each role.
- No existing saved records were deleted; original closed-day and handover records were retained.

## Samples and limits

Hamara Pump Narai: new 18 October Shift 2, duty assignments and closure, returned testing, other income, lube stock/purchase/sale, customer credit/partial repayment, supplier invoices/partial bank payments/credit notes, quality observations, cash float/return, receipt, discount, bulk allocation, salary shortage/adjustment, cash deposit, bank allocation, payment evidence and reviewed day close.

Shree Govind KSK: added suppliers/purchases/payments/credit notes, delivery/quality/dip entries, lube product/opening/purchase, receipt and office expense. Existing shifts, handovers, debtor transactions, discounts and salary adjustments remain. Because handovers were already saved, duty/testing/other-income/cash-movement gaps are represented by explicitly cancelled/reversed synthetic history fixtures. Those inactive fixtures have no financial or stock effect and are NOT evidence that normal entry locks were bypassed through the UI. Active entry/reversal behaviour is tested in temporary databases.

New coverage fixtures use DEMO COVERAGE labels. Bulk allocations, discounts, tax setting, salary-due credits and real money movements remain separate. No bank transaction or wage payment occurred. Tax remains disabled. Each organisation has its own records and references.

## Scenario coverage

The automated suite covers normal integrated shifts, stock and handovers; invalid meter/rate/quantity inputs; duplicate slots/references/submission tokens; excessive credits, discounts, payments and inventory use; partial supplier payment/credits; salary shortage once-only and later-month protection; salary adjustment bounds/stale forms/undo; discounts and bulk no-double-count; returned testing; daily close and SQL date locks; role restrictions; normalized payment CSV conflicts; historical ageing; and encrypted restore/corruption checks.

This is scenario-based testing, not proof of every possible circumstance. Live merchant APIs, actual banking, actual salary/refund payments, direct-tank withdrawals, native merchant file formats, simultaneous multi-operator load and a replacement-PC recovery remain outside this demo verification. The application is not production ready.

## Section inventory

### Hamara Pump Narai

| Model | Demo records |
|---|---:|
| Tank | 2 |
| Nozzle | 8 |
| Shift | 2 |
| Salesperson | 2 |
| DailyFuelPrice | 2 |
| Reading | 16 |
| ManagerProfile | 1 |
| Handover | 2 |
| Debtor | 2 |
| DebtorTransaction | 3 |
| Expense | 4 |
| LubeProduct | 1 |
| LubeSale | 1 |
| SalaryRecord | 1 |
| SalaryDeduction | 1 |
| TankOpening | 2 |
| FuelDelivery | 2 |
| TankDip | 2 |
| AuditEvent | 28 |
| Duty | 1 |
| DutyAssignment | 8 |
| FuelTest | 1 |
| OtherIncome | 1 |
| DigitalCollection | 1 |
| LubeMovement | 2 |
| CashMovement | 2 |
| BankReconciliation | 1 |
| SalesReceipt | 1 |
| NumberSeries | 17 |
| Supplier | 1 |
| FuelPurchase | 2 |
| SupplierPayment | 2 |
| SupplierCredit | 2 |
| StaffAccess | 4 |
| BusinessDayClose | 1 |
| MoneyAccount | 2 |
| MoneyTransfer | 1 |
| BankAllocation | 3 |
| PaymentImportBatch | 1 |
| PaymentEvidence | 1 |
| TankQualityObservation | 4 |
| SalaryShortageAdjustment | 1 |
| ShiftDiscount | 1 |
| BulkSaleAllocation | 1 |

### Shree Govind KSK

| Model | Demo records |
|---|---:|
| Tank | 2 |
| Nozzle | 8 |
| Shift | 4 |
| Salesperson | 3 |
| DailyFuelPrice | 4 |
| Reading | 32 |
| ManagerProfile | 1 |
| Handover | 4 |
| Debtor | 1 |
| DebtorTransaction | 2 |
| Expense | 3 |
| LubeProduct | 2 |
| LubeSale | 1 |
| SalaryRecord | 1 |
| SalaryDeduction | 1 |
| TankOpening | 2 |
| FuelDelivery | 4 |
| TankDip | 4 |
| AuditEvent | 27 |
| Duty | 1 |
| DutyAssignment | 8 |
| FuelTest | 1 |
| OtherIncome | 1 |
| DigitalCollection | 1 |
| LubeMovement | 3 |
| CashMovement | 2 |
| BankReconciliation | 1 |
| SalesReceipt | 1 |
| NumberSeries | 14 |
| Supplier | 1 |
| FuelPurchase | 2 |
| SupplierPayment | 2 |
| SupplierCredit | 2 |
| StaffAccess | 4 |
| BusinessDayClose | 1 |
| MoneyAccount | 2 |
| MoneyTransfer | 1 |
| BankAllocation | 3 |
| PaymentImportBatch | 1 |
| PaymentEvidence | 1 |
| TankQualityObservation | 8 |
| SalaryShortageAdjustment | 3 |
| ShiftDiscount | 1 |
| BulkSaleAllocation | 1 |
