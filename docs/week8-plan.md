# Week 8-1: Apple-style restyle and a card that shows detail on demand (two PRs)

## Goal
Restyle the web UI to the Apple design tokens, and rebuild the info card so it shows a short summary first and
reveals detail only when asked. No change to the agent, tools, prompt or any number shown.

## Design tokens (from the Apple DESIGN.md in VoltAgent/awesome-design-md)
- One accent, Action Blue `#0066cc` (`#2997ff` on dark). Surfaces `#ffffff`, `#f5f5f7`, dark `#272729`. Text `#1d1d1f`.
- System font stack (SF Pro on Apple), body 15px in the side panel and card (17px is too wide for 400px), line height 1.47, small text 14px and 12px. Weights 400, 600 (no 500).
- 8px spacing scale (4, 8, 12, 17, 24, 32). Pill buttons and chips, 18px card radius, 1px hairlines `#e0e0e0`.
- No gradients and no card shadows (the `.ramp` data legend keeps its colour ramp: it is data, not decoration). Sticky or floating bars use backdrop blur. Buttons scale to 0.95 when pressed.
- Light and dark both supported through `prefers-color-scheme`. Keep every existing aria label and focus ring (blue).
- Lexington Themes is not used: it needs a paid licence key and outputs Astro/Tailwind site sections.

## Split
- **8-1a, tokens only:** `style.css` variables and component styles, no DOM or JS change. Dark mode keeps a darker-text accent (`--accent-text`) so white-on-blue stays above 4.5:1; hairlines get a dark value. The 0.95 press scale sits under `prefers-reduced-motion: no-preference`.
- **8-1b, card and layers panel:** the DOM and JS changes below. New card logic goes in `card.js` / `building-card.js`, not `app.js` (already over the ~200-line rule).

## Card redo (8-1b)
1. **Header:** name, one-line subtitle, close button.
2. **Headline row, with named sources.** Block: median price from `metricsCache` (shown only when it exists for the chosen flat type, else omitted), lease left from `metricsCache[flat].blocks[id][2]` when loaded (else the card's "Lease started: YYYY" fact word for word, never computed), facing from `showBuildingFacts` (`facing_label`). BTO, MRT/LRT and school cards: their existing first two facts as returned by `/card`. Missing value: leave it out, never estimate. No new network call and no parsing numbers out of fact strings beyond what the card already renders.
3. **Inline limits.** Each figure keeps its short qualifier next to it ("median, last 24 months", "approximate, per block", "illustrative"). The long limits text, sources and `as_of` lines go in one "About these numbers" disclosure; the layer's "relative colour ramp" line stays beside the ramp.
4. **Section chips** (Prices, Lease, Sun and facing, Schools, Nearby): `aria-expanded` and `aria-controls`, one open at a time, closed by default. A section loads data on first open only, with its own stale guard (like `cardRequest`) so a late response cannot fill a newer card. `aria-live` is on the summary only.
5. **Schools and rings.** Selecting a block draws the rings and school markers by default at radius 2 km, without re-fitting the map (fit only on an explicit press). It reuses the `/schools/{kind}/{id}` response the school list already fetches (`/around` still serves only the radius counts), so no extra request. Rings draw only if `mine === cardRequest` and no chat highlight has arrived since the selection. A radius-chip choice persists across selections as today (`radiusKm` wins over the default rings). A chat-answer highlight replaces the rings (chat wins); a radius chip choice replaces them (radius and rings stay mutually exclusive as today). The old "Show rings and schools" button is removed.
6. **Actions:** the two question buttons become a compact pill row.
7. **Layers panel:** segmented Type/Price/Lease; 3D and sun options sit in a collapsed "View" section.
8. **Mobile:** one scrollable bottom sheet (map stays 42dvh), no horizontal scroll.

## Contract that must not change
Ids `card`, `card-close`, `card-title`, `card-facts`, `card-limits`, `card-actions`, `schools`, `schools-list`, `schools-summary`, `schools-limits`, `radius-counts`, `amenity-pills` (`data-type` on its buttons), `amenity-note`, `amenity-list`, `route-block`, `route-summary`, `route-steps`, `route-limits`, `route-clear`, `points`, `toggle-3d`, `sun-panel`, `sun-date`, `sun-time`, `sun-time-label`, `sun-position`, `building-error`, `card-buildings`, `card-sun`, `budget`, `flat-type`; `data-mode` on the layer buttons and `data-km` on radius buttons; the `cardRequest` stale guard; no `innerHTML`; the `"#b8bdc9"` grey; every aria label and focus ring.

## Out of scope (later PRs)
Auto-3D on tilt and real-time sun, amenity routes (supermarket, MRT, bus), MOP and BTO status. No agent, tool, prompt or grounding change.

## Done when
- `uv run --no-sync pytest` and `ruff` pass. Existing UI tests updated, not weakened. New tests (in `tests/buildings_ui.mjs` or a card test): one section open at a time, data loads once on first open, a stale section response is dropped, and every old figure and its limit text is still in the DOM.
- Checked in a browser at desktop and 375px, light and dark.
- No new dependency, remote font or network call.
