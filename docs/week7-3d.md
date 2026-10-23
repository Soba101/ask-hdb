# Buildings and sun

Use the map's **3D** button to tilt the map and show HDB outlines. The date and time controls
move the light and show the sun's compass azimuth and altitude in Singapore time (+08:00).
Price and Lease keep their existing colours and budget filter. In Type mode, grey to yellow
shows increasing exposure on the sunnier of the block's two long facades. Turning 3D off
restores the point layer, previous pitch and light. A building click uses the same block
selection, card and chat context as a point click.

Run this offline before building the Docker image:

```sh
uv run --no-sync python scripts/build_buildings.py
```

The builder reads `data/raw/places/hdb_buildings.geojson`,
`data/raw/property/hdb_property_information.csv`, and the clean blocks and resale parquet
tables. It writes `data/clean/buildings.geojson` and prints match and height-source counts.
Docker includes that clean file and checks it exists; `.dockerignore` excludes all raw data.
The generated file is git-ignored, so rebuild it in each checkout used to build an image.

Outlines join only by postal to a unique block ID; missing or ambiguous postals are omitted.
Heights use the HDB property information top floor, matched by block number and normalised
street. Missing heights use the highest recorded resale storey band, then a default of
four floors. The source is shown in the card. Metres are illustrative: floors multiplied by
2.8, not a surveyed roof height. The exact top floor can be lower than the top of a resale band.

Facing is perpendicular to the long axis of a minimum-area rectangle in local metre
coordinates. Multiple outlines for one block are kept as a MultiPolygon with one rectangle
around their exterior points. Output coordinates are rounded to six decimal places and
nearly collinear vertices simplified with a small metre tolerance; collapsed sliver holes are
omitted. The two facade bearings
are approximate per block. Irregular, square and multi-wing blocks may have other facades;
there is no unit-level facing or price.

`/sun?date=YYYY-MM-DD` uses NOAA-style fractional-year solar equations at Singapore's centre,
with quarter-hour samples. `/sun/block/{key}` computes cosine incidence on each vertical
facade, sampled direct-sun hours and first peak time. Dates default to today in Singapore.
This is **illustrative geometry, not measured heat**. It ignores shade from other blocks,
clouds, atmospheric refraction, balconies and local terrain. The light does not cast building
shadows. Hours are sampled, not precise sunrise/sunset integration; the same solar position
is used across Singapore. The model does not calculate these facts.

Block cards also show recorded resale medians for three-storey bands over the latest
24 months in the dataset, only with at least five sales per band. All flat types are pooled,
so size, type and condition can explain differences. Wider recorded bands are omitted
rather than assigned to invented floors. These are historical summaries, not unit-level
valuations or forecasts.

**Coverage.** 9,202 of the 9,496 blocks (97%) have a building, and 9,202 of the 13,436 outlines (68%) are used; the rest are probably not residential blocks (not checked). The outline file is from around 2013, so newer blocks may lack one. Blocks without an outline stay as points in 3D, with no height or facing.

`/map/buildings` is compressed once and kept in memory (compressing per request blocked the server for seconds). A missing file returns
a clear error; ordinary block cards still work without building metadata. The CSP is unchanged,
and page additions render data with text nodes. Agent, tool, prompt, grounding and eval
behaviour are unchanged; no model eval is required for this map addition.
