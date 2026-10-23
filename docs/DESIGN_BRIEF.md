# Owner dashboard redesign brief

Recorded from the owner's answers on 23 October 2026. These are design requirements, not claims that the redesign has been implemented.

## Confirmed priorities

- Primary user: the owner.
- Most important information: sales.
- Daily shift closing: handled by the manager; the exact steps still need clarification.
- Shortages: handled by admin; approval and correction rules still need clarification.
- Primary device: phone.
- First screen to focus on: owner dashboard.

## Design direction to evaluate

Give the owner a clear sales view on a phone, with visible station and business-date context. Show whether figures are complete and when they were checked. Keep the manager's entry workflow accessible separately. Preserve the distinction between sales, money collected, and pending digital settlements.

The reference article distinguishes layout, typography and accessible controls from interaction feedback and motion. Use those ideas to support daily work; do not assume an Apple visual style is itself a requirement. Reference: https://glamorous-pencil-2e4.notion.site/Make-Claude-Design-to-Apple-s-Standard-The-Two-Skills-3f6f8ee1272181bd8c0df0df5f912e8a

No third-party design skills were installed during the repository import.

## Next questions for the owner

1. Should sales mean rupees, litres, or both? Should the main total include fuel only or fuel plus lubes and other income?
2. On opening the app, should both stations be combined, compared side by side, or should one station open first?
3. Should the initial date be today even if incomplete, or the latest completed day? Should the comparison be yesterday, the same weekday last week, or a monthly target?
4. Besides sales, which two items belong on the first screen: shortage, cash, pending digital settlements, tank stock, customer dues, or closing status?
5. What does the manager actually submit at closing, and what must admin do when there is a shortage?

## Boundaries for implementation

Keep existing business rules, station separation, historical records and role permissions intact. Record any proposed permission changes explicitly before implementation. Do not hide incomplete or unverified figures behind a successful-looking dashboard. Validate the eventual layout and interactions at phone widths using actual rendered screens.
