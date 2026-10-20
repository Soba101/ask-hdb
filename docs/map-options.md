# Map display options (noted 2026-10-21)

OneMap is used only to geocode (turn an address into coordinates). The map users see in the web app (week 6)
is a separate layer: MapLibre or Mapbox GL with a tile provider. Choosing a look does not change the geocoding.

| Option | Look | Cost and catches |
|---|---|---|
| MapTiler or OpenFreeMap (via MapLibre) | Clean modern styles, 3D buildings | Free tier; OpenFreeMap needs no key. Building heights come from OpenStreetMap and are patchy in Singapore. |
| Mapbox | Probably the best-looking, good 3D, built-in lighting and shadows (Standard style) | Needs a key; free tier of about 50k map loads a month, then paid. |
| Google Maps | Photorealistic 3D city tiles | Needs billing; its terms limit storing results, so display only, never our coordinate cache. |
| Apple Maps (MapKit JS) | Very polished | Needs a paid Apple developer account (about US$99 a year); web 3D is more limited than on iPhone. |

Default: MapLibre with MapTiler (or OpenFreeMap), Mapbox as the upgrade if shadows or polish matter. Decide in week 6 by trying two
styles on real blocks.

## Simulating a new BTO location
Feasible
- Mark the site (point or approximate footprint) and show straight-line distance to the nearest MRT and primary schools, plus nearby existing blocks.
- Placeholder extruded blocks at an assumed height, labelled "illustration, not the real design".
- Sun and shadow by time of day (Mapbox Standard style has it built in; MapLibre needs custom work).
- Planned MRT stations from the URA Master Plan rail station layer on data.gov.sg (not downloaded yet).

Not feasible
- The real design: HDB does not publish footprints, heights or layouts for upcoming BTO. Launch pages give a site, a rough location, flat counts and a completion date.
- Exact facing or views for a unit.
- Other new or under-construction developments nearby: OpenStreetMap lags behind.

Fits with week 4b (BTO) and the week 6 web app. See issue #24.

## Other notes from the same discussion
- Floors for a 3D map: the HDB building outlines have none; the data.gov.sg "HDB Property Information" dataset (max floor level) may, not yet checked (issue #19).
- Facing can only be estimated from a block's outline, labelled approximate. Sun, noise and views are not in our data.
