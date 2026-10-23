# Station setup audit and isolated pilot

Verified on 19 October 2026.

## Actual saved setup

Hamara Pump Narai has two DEMO tanks with saved capacities of 20,000 litres each. Nozzles 1-4 are mapped to petrol and 5-8 to diesel; actual capacities and physical connections remain unverified. Mohan is an active salesperson and Durgesh is an active manager profile. One first shift exists. Tank openings, cash/bank openings and lube products are absent.

Shree Govind KSK has no tanks, nozzles, manager profile or openings configured. Kapil is an active salesperson. Both installations have owner/superadmin logins, with no explicit staff-role assignments.

Unknown stock, balances, measurements and staff credentials were not invented. Existing records were preserved. The owner-only Setup readiness screen now shows these gaps with links to the appropriate screens.

## Isolated rehearsal

The synthetic pilot runs inside Django's temporary test database. It covers two complete shifts, lube stock and sales, customer credit and repayment, shift/station expenses, payment evidence, bank settlement, bank allocation, cash deposit, tank delivery/dips, morning/after-delivery quality records, independent manager review and closed-day write rejection. No synthetic entries are inserted into operational databases.

104 full-suite tests passed. This is software workflow verification, not a physical stock check or a real-world acceptance pilot. Actual setup still requires measured tank/lube quantities, actual account balances with an opening date, verified equipment mapping and intended staff logins/roles.
