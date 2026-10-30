# UI/UX test plan (2026-10-29)

Written from the code by a review agent, following Apple's Human Interface Guidelines and accessibility guidance. Contrast ratios were computed from the hex values in `style.css`;
for see-through panels the map was assumed to be #f2f2f2, #9a9a9a or #2a2a2a. Nothing here was run in a browser by the author.

## Core tasks

| # | Task | Success | Metric |
|---|---|---|---|
| T1 | Find what a 4-room costs near a given MRT | Gives the correct median and its source | Under 3 min, no help |
| T2 | Check eligibility, then confirm "Is this right?" | States the result and its conditions | Completion, errors |
| T3 | See the walk from a block to the nearest MRT | Route shows, reads the minutes | Taps to the route |
| T4 | Say why an answer is trusted | Opens Evidence and names a tool or source | Share who find it with no hint |
| T5 | Colour blocks by price under a budget | Sets the slider, explains grey vs coloured | Ease score 1 to 7 |
| T6 | Primary schools within 1 km | Names them, knows distances are straight-line | Correct count |
| T7 | Lease left and MOP status | Reads the years left and the caveat | Correct answer |
| T8 | Wait 60 s, then ask a follow-up | Does not leave, refresh or press Send again | Drop-out rate, felt wait |
| T9 | Recover from a network error | Retries without retyping | Time to recover |
| T10 | Pick from "Which one do you mean?" | Selects the correct place | Errors |

## Findings (before the fixes)

- **Contrast fails:** #0071e3 on the light fill is 4.09 (desktop) and 4.05 (phone), 4.0 over a mid-grey map; #2997ff on the dark fill is 3.76 (desktop) and 4.23 (phone). The limit is 4.5.
  `--muted` passes everywhere. White on #0071e3 is 4.70.
- **No Increase Contrast or Reduce Transparency rules.** All sizes are px, so iOS text size likely has no effect.
- **Touch targets:** the map attribution button is 32 px; the desktop close buttons are about 20 x 36.
- **Keyboard:** only a pointer click selects a place on the map; the highlighted-places list is plain text.
- **ARIA:** the chat log is a polite live log. The Chat and Evidence toggles are buttons, not a tablist. The sheet handle has no `aria-expanded`.
- **Reduce Motion:** CSS animations and Sun Play obey it; map moves and the 3D tilt do not.
- **Esc:** steps the sheet down on the phone only. On desktop it does not close the card or stop a request.
- **The 60 s wait:** a visible "Working on it... Ns" timer runs, but it is `aria-live="off"`, there is no Cancel, and tool results stream into a hidden Evidence tab.
- **Errors:** the question box is cleared before the request is sent, so a failure loses the text. A network failure shows raw browser text. No Retry button.
- **Empty chat:** no example questions.

## Automated checks (Node DOM harness or a console script)

1. Contrast of every text colour on its fill, per mode, at least 4.5:1.
2. Exactly one `aria-pressed="true"` per segmented group after each click.
3. A polite live status exists during a request.
4. A Cancel button aborts a request and re-enables Send.
5. A failed request leaves the question in `#question`.
6. Escape hides `#card` on desktop.
7. `#sheet-content` is inert at peek.
8. With reduced motion, map moves use duration 0.
9. At 375 px with touch, no visible control is under 44 x 44.
10. Every visible button has an accessible name.
11. Each layout has one visible h1 and skips no heading level.

## Manual script (20 minutes)

**iPhone:** 0 to 3 min T1 unaided; 3 to 8 min VoiceOver on, T3 and T8 (is the wait announced?); 8 to 11 min largest text size and Bold Text; 11 to 14 min Dark mode, Increase Contrast,
Reduce Transparency; 14 to 17 min Reduce Motion, T6; 17 to 20 min landscape, keyboard against the safe areas, Airplane mode, T9.
**Mac:** keyboard only for T2, T4, T10 and selecting a block; Esc on the card and during a wait; VoiceOver through a full 60 s wait; 200% zoom; focus ring in Dark mode.
