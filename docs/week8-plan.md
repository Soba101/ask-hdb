# Week 8-1: Apple-style restyle and a card that shows detail on demand

## Goal
Restyle the web UI to the Apple design tokens, and rebuild the info card so it shows a short summary first and
reveals detail only when asked. No change to the agent, tools, prompt or any number shown.

## Design tokens (from the Apple DESIGN.md in VoltAgent/awesome-design-md)
- One accent, Action Blue `#0066cc` (`#2997ff` on dark). Surfaces `#ffffff`, `#f5f5f7`, dark `#272729`. Text `#1d1d1f`.
- System font stack (SF Pro on Apple), body 17px / line height 1.47, small text 14px and 12px. Weights 400, 600 (no 500).
- 8px spacing scale (4, 8, 12, 17, 24, 32). Pill buttons and chips, 18px card radius, 1px hairlines `#e0e0e0`.
- No gradients and no card shadows. Sticky or floating bars use backdrop blur. Buttons scale to 0.95 when pressed.
- Light and dark both supported through `prefers-color-scheme`. Keep every existing aria label and focus ring (blue).
- Lexington Themes is not used: it needs a paid licence key and outputs Astro/Tailwind site sections.

## Card redo (replaces the current card in `index.html`, `app.js` showCard, `building-card.js`)
1. **Header:** name, one-line subtitle (town, flat count or type), close button.
2. **Headline row:** 3 key figures at most (for a block: median price for the chosen flat type, lease left, facing). Each from the tool result already used today.
3. **Chips that open sections:** Prices, Lease, Sun and facing, Schools, Nearby. Only one section open at a time, collapsed by default. A section loads its data when first opened.
4. **Schools:** rings and school markers are drawn as soon as a block is selected (no "Show rings and schools" button). The radius chips stay and default to 2 km. The school list is a section, not always visible.
5. **Footnotes and limits:** moved into a single "About these numbers" disclosure at the bottom, text unchanged.
6. **Actions:** "3 nearest schools" and "recent resale prices" become a compact row of pill buttons.
7. The floating layers panel gets the same treatment: segmented control for Type/Price/Lease, 3D and sun options in a collapsed "View" section.
8. Mobile: the card becomes a bottom sheet with two heights (summary, expanded), no horizontal scroll.

## Out of scope for this PR (later PRs)
Auto-3D on tilt and real-time sun, amenity routes (supermarket, MRT, bus), MOP and BTO status.

## Done when
- `uv run --no-sync pytest` and `ruff` pass. UI tests (`tests/buildings_ui.mjs` and the card tests) updated, not weakened.
- Every figure on the old card is still reachable, with its source and limit text.
- Checked in a browser at desktop and 375px width, light and dark.
- No new dependency, no remote font, no network call added.
