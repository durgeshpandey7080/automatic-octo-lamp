# Owner dashboard redesign brief

Updated from the owner's answers and accepted recommendations on 23 October 2026. These are design requirements, not claims that the redesign has been implemented.

## Confirmed priorities

- Primary user: the owner, Durgesh, who is also the admin reviewing shortages.
- Most important information: sales in both rupees and litres, covering both pumps.
- Default business date: today, including incomplete submissions.
- Comparison: the same weekday last week.
- Secondary dashboard priorities: cash balance and tank stock.
- Managers submit each shift and physically count cash after every shift.
- Durgesh approves the daily closing.
- Tank dip is measured daily at Shift 2 closing.
- Primary device: phone.
- First screen to focus on: owner dashboard.

## Accepted operational recommendations

### Shortages and review

Require the manager to explain a cash shortage before submitting the shift. Durgesh reviews it and can return it for correction or approve with a recorded reason. Approval must preserve the shortage, explanation and review history; it must not silently clear the discrepancy or imply an automatic salary deduction.

### Cash custody and retained change

Cash normally remains with the manager until deposited in the bank. If it cannot be deposited, it may be handed to Durgesh, Shivakant, Umakant or Krishnakant. Track custody by person and originating pump, rather than assuming cash remains physically at the pump.

Some cash is always retained as change. Following the owner's acceptance of the recommendation, record the actual amount retained at every shift handover rather than assuming a fixed amount for either station. Carry that amount forward as the next shift's opening cash. This is a design default, not evidence that the amount varies on every shift.

Show total cash on hand with an expandable breakdown of drawer/change cash and amounts held by the manager or named recipients. A custody transfer changes the holder, not total cash, revenue or expenses. Record sender, recipient, amount, business date/time and receipt acknowledgement. Keep an unacknowledged transfer visible without counting the amount with both holders.

Track deposits with the destination bank account and reference. Distinguish cash physically held, deposits awaiting confirmation, and confirmed bank balances. Posting and reversal rules must prevent a deposit being counted as both available cash and bank funds. These UI requirements still need to be mapped to the existing ledger implementation.

### Acknowledgements, access and corrections

Support both recipient acknowledgement and confirmation by Durgesh on a recipient's behalf. Require a reason for owner confirmation and distinguish the two actions in the history. Record the actual actor and timestamp. Transfers stay Pending acknowledgement until confirmed, with the money counted exactly once.

Managers see their assigned station; Durgesh sees both. A cash recipient without a management role sees only their own handovers and balances, including separate originating-station balances if holding money from both pumps. Enforce this on the server, not just through navigation. Account provisioning remains a separate task; names alone are not login accounts.

Lock a shift after submission. Subsequent corrections require a manager request with a reason and owner approval, preserving original values and change history. Keep this shift submission distinct from the owner's daily closing approval.

The manager or person holding cash records a bank deposit with amount, destination account, reference and receipt evidence. Durgesh confirms reconciliation against bank evidence. Do not grant unrelated station-management permissions merely to allow deposit entry.

### Shift schedule and business dates

Use Asia/Kolkata local time. Shift 1 runs from 10 PM on the previous calendar date to 10 AM on the business date; Shift 2 runs from 10 AM to 10 PM on that business date. Label both with the date on which Shift 2 closes. The current business period advances at 10 PM; keep the just-ended period visible if awaiting submission or approval rather than hiding it when the date changes. Never relabel existing records silently.

Expected closes are 10 AM and 10 PM. Apply the accepted 30-minute grace period: an outstanding shift becomes overdue after 10:30 AM or 10:30 PM. Before its deadline it is pending, not overdue. Show overdue shifts prominently on the owner's dashboard. Allow late submission with a required reason and preserve the server-recorded submission timestamp. Schedule these as in-app states; no external messages or recurring automation have been requested.

### Stock alerts

Use a configurable threshold per tank, initially 5,000 litres, with separate petrol/diesel settings where appropriate. This is a warning threshold, not a stock opening balance or an invented physical reading. Validate against actual tank capacity during setup rather than silently assigning an unusable threshold.

Normal delivery is the next day after ordering. Show litres remaining and estimated coverage from recent complete sales days, with the lookback and data cutoff visible. Raise an additional warning if projected runout precedes expected delivery even when stock exceeds 5,000 litres. Next-day delivery is the normal lead time, not proof of an order or a confirmed delivery time. Keep unavailable/insufficient sales history distinct from zero consumption. Dips remain measured daily at Shift 2 close.

### Connection and submission feedback

For the first version, show a clear connection failure and preserve unfinished form input where feasible. Display Submitted only after server confirmation. A lost response can leave the result unknown; check the server's submission status before retrying and prevent duplicate posting. Do not claim that browser-held drafts are submitted or approved records. Full offline submission/synchronisation is outside this first redesign.

## Design direction to evaluate

Give the owner a clear sales view on a phone, with visible station and business-date context. Show whether figures are complete and when they were checked. Keep the manager's entry workflow accessible separately. Preserve the distinction between sales, money collected, and pending digital settlements.

The reference article distinguishes layout, typography and accessible controls from interaction feedback and motion. Use those ideas to support daily work; do not assume an Apple visual style is itself a requirement. Reference: https://glamorous-pencil-2e4.notion.site/Make-Claude-Design-to-Apple-s-Standard-The-Two-Skills-3f6f8ee1272181bd8c0df0df5f912e8a

No third-party design skills were installed during the repository import.

## Proposed presentation defaults

These are recommendations for the first design, not additional implemented business rules:

- Combined sales first, followed by vertically stacked station cards on a phone.
- Main sales figure covers fuel; petrol and diesel litres appear separately. Show lubricants and other income separately rather than silently mixing them into fuel sales.
- Compare matching submitted shifts with the same weekday last week. Label the actual dates and coverage. Suppress a percentage when the baseline is missing or zero.
- For missing submissions, show which shift is awaited, last submission time and an Incomplete label. Do not substitute zero for missing data; use an error state only for an actual failure.
- Show calculated cash alongside the latest physical count, with the count's time and difference. Reconcile custody movements since the count before presenting a current discrepancy.
- During the day, calculated stock and the previous measured dip must retain their distinct timestamps. At Shift 2 closing, compare book stock and the new dip for the same cutoff.
- Bring sales, cash differences, stock differences and manager explanations together in the owner's closing review. Missing mandatory records should block closing; explained discrepancies require an explicit owner decision and reason. Exact validation rules remain to be checked against the existing implementation.

## Discovery checkpoint

The owner has accepted the operating defaults above. There is enough direction for the first phone dashboard design. The implementation plan is in `REDESIGN_PLAN.md`; a requirement in this brief is not evidence that the running app already supports it.

## Boundaries for implementation

Keep existing business rules, station separation, historical records and role permissions intact. Record any proposed permission changes explicitly before implementation. Do not hide incomplete or unverified figures behind a successful-looking dashboard. Validate the eventual layout and interactions at phone widths using actual rendered screens.
