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

## Next question for the owner

When a named person receives cash, can they log in and acknowledge receipt themselves, or must Durgesh confirm it? Names in this brief do not authorize creating accounts or granting access. The acknowledgement workflow must fit who actually uses the application.

## Boundaries for implementation

Keep existing business rules, station separation, historical records and role permissions intact. Record any proposed permission changes explicitly before implementation. Do not hide incomplete or unverified figures behind a successful-looking dashboard. Validate the eventual layout and interactions at phone widths using actual rendered screens.
