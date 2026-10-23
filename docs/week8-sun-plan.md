# Week 8-3: 3D appears when you tilt, and the sun is live

## Goal
1. The 3D buildings switch on by themselves when the user tilts the map, and the flat map returns when the map is level again.
2. The sun is "real time": a Now button (Singapore time), a play button that runs the day, and shadows that move with it.
3. Parts of a block are lit or dark: each wall is shaded by its own direction, and buildings cast shadows on the ground and on each other.

## Prior art
ShadeMap (shademap.app, Ted Piotrowski) and `mapbox-gl-shadow-simulator` render shade from a height raster on the GPU. They are built for terrain and need either a licence or a DEM source, so they are not a fit for HDB footprints. We do the same idea analytically on the outlines we already ship.

## Design
- **Auto 3D.** On `pitchend`, pitch above 10 degrees enables 3D (loads `/map/buildings` once, as the toggle does today) without forcing a pitch; pitch back below 3 degrees disables it. The 3D button stays as a manual override. A manual choice is kept until the user next tilts or levels the map. Mobile: a two-finger tilt does the same; a "3D" button remains in the View section.
- **Per-wall shading.** The extrusion layer already lights each wall by `map.setLight` with the sun direction. Raise the light intensity and colour contrast so a wall facing away from the sun is visibly darker than one facing it, even in Type mode. The per-building exposure colour (grey to yellow) is kept as an option, not the default.
- **Shadows.** In `src/ask_hdb/api/static/shadows.js`: for each building near the viewport (zoom 15 or more, at most about 600 buildings) project its footprint along the sun's ground direction by length `height_m / tan(altitude)` and take the convex hull of the footprint and its shifted copy. Draw those as one translucent fill layer under the extrusions. No shadow when the sun is below 5 degrees. Recompute on `moveend` and when the time changes, throttled with `requestAnimationFrame`, work capped per frame.
- **Real time.** A "Now" button sets date and time to the current Singapore time (UTC+8, not the browser's zone). A play button advances 15 minutes of sun per animation step (about 8 s for a day) and pauses on any manual input or when the tab is hidden. `prefers-reduced-motion` disables play.
- **Honest labels.** Shadows are illustrative: convex hull of each footprint (overestimates concave blocks), no trees, no clouds, overlapping shadows may look darker, heights from floor counts. The existing limit text is updated; "no shade from other blocks" is replaced by this wording.
- No change to the Python API, the agent, tools or prompts. No new dependency, no network call beyond the existing `/map/buildings` and `/sun`. No `innerHTML`.

## Contract that must not change
All ids and behaviours listed in docs/week8-plan.md, plus the mobile Layers overlay (docs: mobile PR), `wallExposure` parity with `ask_hdb/sun.py`, the existing sun tests, and the stale-response guards.

## Done when
- pytest and ruff pass; new offline tests: auto-3D on/off thresholds and manual override, Now uses UTC+8, play pauses on input and when hidden, shadow polygons correct for a known case (a 30 m building, sun at 45 degrees, shadow length 30 m opposite the sun), no shadow below 5 degrees, work cap respected.
- Checked in a browser: tilt turns 3D on, a block shows a lit and a dark wall, shadows move with the slider, desktop and 375px.
