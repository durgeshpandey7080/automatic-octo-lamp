# Operations guide - Pandey Petrol Pump

Choose the organisation before entering records. All entries below stay in that
organisation's database. Both databases were backed up before this update.

## 1. Open cashier duty

Open Operations ledger -> Open duty. Enter date, shift, daily fuel rates, and all
eight nozzle assignments/openings. These are saved drafts, not sales. Closing
entry pre-fills them; the server rejects a different staff/opening/rate. Cancel an
incorrect open draft with a reason; its audit record remains. A closed duty cannot
be cancelled. Direct completed-shift entry remains available for older workflows.

## 2. Returned testing fuel

After closing readings are recorded but before any handover or closing dip, record
the tested quantity for the correct reading. All test fuel is returned to the same
tank. Billable litres = closing - opening - testing. Net tank outflow = closing -
opening - returned testing. Testing therefore reduces revenue and restores fuel
to stock. It never changes the saved cumulative meter counters. Correction requires
a staff user and a reason; handovers, dips and issued receipts can lock it.

## 3. Detailed customer credit

Credit slips now have optional vehicle, petrol/diesel, quantity and saved rate.
If detailed quantity is entered, quantity times rate must equal the credit amount,
and the rate/quantity must fit that salesperson's actual shift sales. Historical
amount-only credits remain unchanged. Credit is an allocation of existing sales,
not another sale. Repayments continue through the debtor account.

## 4. Other income and digital transactions

Other-income vouchers add once to the person's assigned shift revenue. Record
its actual digital payment too if it was not cash. Each digital/POS transaction
has an automatically generated internal voucher and a manually entered real
bank UTR/POS reference. Once transaction records are used, the handover provider
fields are read-only totals of those records: enter ALL digital collections for
that person/shift, not only a sample. Legacy saved handover amounts stay intact.

## 5. Lube stock

Activate inventory once with opening quantity (zero is allowed), then record
purchases. Inventory activation excludes earlier legacy sales already covered by
your physical opening count. Later lube sales reduce stock; overselling is blocked.
Use actual product units. Reorder levels show low-stock warnings. Purchase unit
cost and supplier invoice are recorded, but this is not a supplier-payables ledger.
Positive/negative stock adjustments require notes. Wastage cannot exceed stock.

## 6. Cash, bank and audit

Float/office receipts increase expected cash; cash returned to a manager decreases
final handover cash. They are transfers, not income/expenses. Enter these against
the saved shift before handover. Expected final cash = sales + other income -
credit - expenses - digital collections + incoming transfers - cash returned.
Earlier cash returns appear in the receiving manager's submitted cash separately
from the final handover; cash issued by the manager is shown separately.

Bank matching records the actual settlement reference, net credit and fee. Net
plus fee must equal the digital collection. It is manual matching, not a bank API.
Fees are not automatically posted as another expense. Reversals retain originals,
actor, reason and time; settled handovers and reconciled collections stay protected.
This is an operation audit, not a comprehensive tamper-proof audit system.

## 7. Receipts; tax and discounts disabled

Issue an ordinary sales receipt from one saved fuel reading or lube sale. It does
not add sales or confirm payment. Fuel quantity cannot exceed uninvoiced sold
litres. Lube sales have at most one active receipt. Voiding retains the receipt.
Tax/discount computations and GST invoice labelling remain disabled at the user's
request; no tax eligibility or exemption is inferred for other products.

## Automatic document numbers

New internal numbers follow ORGANISATION/TYPE/YEAR/SEQUENCE, e.g.
HPN/BILL/2026/000001 or SGK/CR/2026/000001. Sequences are separate per organisation,
document type and year. Credit slips, repayments, expenses, lube sales, deliveries,
handovers and operations vouchers are generated on save. Existing references are
not renumbered. Supplier invoice, bank UTR, bank settlement and POS references are
external identifiers and remain manually entered. Failed entries roll back numbers
with the operation. Keep the number-series table in database backups.

## Superadmin

The new superadmin account has Django superuser access in both organisations and
uses the central login/chooser. Its credentials are outside the source ZIP in
../SUPERADMIN-LOGIN.txt. Full application permissions do not bypass settled-ledger
validation rules. Owner account/password management remains coordinated across the
two local databases; this is not a hosted identity-management service.

## Limits

For trusted local use only. Corrections to settled meter readings need a controlled
developer workflow; they cannot be silently overwritten. No live bank integration,
supplier accounts payable, bulk-sale reconciliation or tax engine is included.

## Supplier accounts update
Fuel purchase supplier accounts are now available. See README.md for the invoice-to-delivery linkage, partial payments, agreed credits and reversal workflow. The earlier limitation about supplier payables is superseded for this limited invoice-based workflow; advances, refunds and a full cash/bank ledger remain unsupported.
