# Week 8-4: Google Maps-style phone layout

## Goal
On phones (width 800px or less) the app feels like Google Maps: a full-screen map, a floating search bar, a row of layer chips, and one bottom sheet that holds everything else. Desktop (above 800px) is unchanged.

## Layout
- **Map:** full screen (100dvh). The side panel no longer takes space below the map.
- **Search bar (top, floating):** the chat input. Tapping it opens the sheet at full height on the Chat tab with the keyboard up. A clear button and the "Asking about: ..." chip live inside it when a place is selected.
- **Chip row (below the search bar, horizontal scroll, no scrollbar):** Type, Price, Lease, 3D. Price shows its flat type and budget in a small popover under the chip, not inline. The Layers button and overlay from the earlier mobile PR are replaced by this row.
- **Bottom sheet, three snap points:** peek (about 112px, shows a drag handle plus the title and the headline figures of the selection, or "Ask about a flat, a grant or a place" when nothing is selected), half (50dvh), full (92dvh). Drag the handle or the header to move between them; releasing snaps to the nearest point with a small velocity bias; tap the handle to step up. Pointer events with `touch-action: none` on the handle only, so the content scrolls normally and the map still pans.
- **Selecting a place** opens the sheet at peek with the card summary; tapping the section chips (Prices, Lease, Sun and facing, Schools, Nearby) lifts it to half. Closing the card returns the sheet to the chat peek. Chat answers lift it to half and show the answer; the Evidence tab sits in the sheet header next to Chat.
- **Sun and 3D:** when 3D is on, a slim bar (time label, slider, Now, Play) docks above the sheet's peek. The long limit text moves under an "About the sun view" disclosure inside the sheet. Map controls (zoom, compass/tilt) sit at the right above the sheet, never covered by it; the attribution stays visible.
- **Rings and highlights** keep working; the map padding is set to the sheet's height so the selected place is centred in the visible map, not behind the sheet.
- Sizes: 44px touch targets, 16px inputs, safe-area insets for the top bar and the sheet, no horizontal scroll at 320 to 430px, landscape phones use the half height cap at 60dvh.

## Rules
- Same DOM ids and behaviours as docs/week8-plan.md; the sheet reuses `#card`, `#chat`, `#evidence`, `#layers` content, moved or re-parented in CSS and a small controller (`src/ask_hdb/api/static/sheet.js`), not rebuilt. No `innerHTML`, no new dependency, no network or API change, no change to the agent, tools or prompt.
- Accessibility: the sheet is a labelled region; the handle is a button with `aria-expanded` and keyboard support (Enter, Space, ArrowUp and ArrowDown change the snap point); focus moves into the sheet when it opens; Escape steps down one snap point; reduced motion disables the snap animation; `aria-live` stays on the card summary only.
- All limits, sources and `as_of` text stay reachable (inside the sheet, under the existing disclosures).

## Done when
- pytest and ruff pass. Offline tests (new `tests/sheet_ui.mjs`, wired through `tests/test_buildings_ui.py`): snap-point selection from drag distance and velocity, keyboard steps, sheet follows selection and closing, chip row replaces the Layers overlay on phones only, the sun bar shows only when 3D is on, desktop DOM behaviour unchanged.
- Checked in a 375px browser (light and dark): search bar, chips, all three sheet heights, card sections, 3D bar, no covered controls.
