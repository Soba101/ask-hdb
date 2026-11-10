// Display geometry only. These shadows never feed the facade or direct-sun figures.
const EMPTY = { type: "FeatureCollection", features: [] };
const radians = (degrees) => degrees * Math.PI / 180;
export function shadowOffset(height, sun, latitude) {
  const length = Math.min(Math.max(0, height) / Math.tan(radians(sun.altitude)), 300);
  // Exact compass axes avoid tiny floating-point slivers along rectangular walls.
  const axis = (value) => Math.abs(value) < 1e-12 ? 0 : value;
  return [-axis(Math.sin(radians(sun.azimuth))) * length / (111320 * Math.cos(radians(latitude))),
    -axis(Math.cos(radians(sun.azimuth))) * length / 110540];
}
const signedArea = (ring) => ring.reduce((sum, p, i) => i ? sum + ring[i - 1][0] * p[1] - p[0] * ring[i - 1][1] : 0, 0) / 2;
// An extruded flat roof shades P plus the sweep of each edge that faces away from the sun.
// From any shaded point, a step back toward the sun enters P through one of those edges.
function sweep(polygon, offset) {
  const rings = polygon.map((ring, i) => (signedArea(ring) > 0) === (i === 0) ? ring : [...ring].reverse());
  const quads = [];
  for (const ring of rings) {
    for (let i = 1; i < ring.length; i++) {
      const a = ring[i - 1], b = ring[i];
      // Outward normal of a CCW outer ring (and of a CW hole) is (dy, -dx). Metre scales are a positive factor.
      if ((b[1] - a[1]) * offset[0] - (b[0] - a[0]) * offset[1] <= 0) continue;
      const a2 = [a[0] + offset[0], a[1] + offset[1]], b2 = [b[0] + offset[0], b[1] + offset[1]];
      quads.push([[a, b, b2, a2, a]]);
    }
  }
  return [rings, ...quads];
}
function parts(feature) {
  const { type, coordinates } = feature.geometry;
  return type === "MultiPolygon" ? coordinates : type === "Polygon" ? [coordinates] : [];
}
export function shadowPolygons(feature, sun) {
  if (!sun || sun.altitude < 10) return [];
  return parts(feature).flatMap((polygon) => {
    const latitude = polygon[0][0][1], offset = shadowOffset(feature.properties.height_m, sun, latitude);
    return [{ type: "Feature", properties: { block_id: feature.properties.block_id },
      geometry: { type: "MultiPolygon", coordinates: sweep(polygon, offset) } }];
  });
}
function bounds(feature) {
  const vertices = parts(feature).flatMap((p) => p[0]);
  return vertices.reduce((b, [x, y]) => [Math.min(b[0], x), Math.min(b[1], y), Math.max(b[2], x), Math.max(b[3], y)],
    [Infinity, Infinity, -Infinity, -Infinity]);
}
export function shadowCollection(index, sun, viewport, zoom) {
  if (!sun || sun.altitude < 10 || zoom < 15) return EMPTY;
  const { west, south, east, north } = viewport;
  // A caster outside the view can reach into it only from the sun's side.
  const toward = shadowOffset(300, { ...sun, altitude: 45 }, (south + north) / 2).map((v) => -v);
  const view = [west + Math.min(0, toward[0]), south + Math.min(0, toward[1]),
    east + Math.max(0, toward[0]), north + Math.max(0, toward[1])];
  const selected = index.filter(({ box: b }) => b[2] >= view[0] && b[0] <= view[2] && b[3] >= view[1] && b[1] <= view[3]).slice(0, 600);
  return { type: "FeatureCollection", features: selected.flatMap(({ feature }) => shadowPolygons(feature, sun)) };
}
export function initShadows(map, outlines) {
  const index = outlines.features.map((feature) => ({ feature, box: bounds(feature) }));
  let enabled = false, sun = null, frame = null, dirty = false;
  map.addSource("shadows", { type: "geojson", data: EMPTY });
  // A flat extrusion blends once per layer, so overlapping wall sweeps do not stack into darker stripes.
  map.addLayer({ id: "shadows", type: "fill-extrusion", source: "shadows", minzoom: 15,
    paint: { "fill-extrusion-color": "#182333", "fill-extrusion-opacity": 0.4, "fill-extrusion-height": 0.1,
      "fill-extrusion-vertical-gradient": false }, layout: { visibility: "none" } }, "blocks");
  function schedule() {
    if (!dirty || frame !== null) return;
    frame = requestAnimationFrame(() => {
      frame = null;
      // Wait for the worker to finish the last whole collection. No mixed-time partial writes.
      if (!map.isSourceLoaded("shadows")) return;
      dirty = false;
      const b = map.getBounds();
      map.getSource("shadows").setData(enabled ? shadowCollection(index, sun,
        { west: b.getWest(), south: b.getSouth(), east: b.getEast(), north: b.getNorth() }, map.getZoom()) : EMPTY);
    });
  }
  function refresh() { dirty = true; schedule(); }
  map.on("move", () => { if (enabled) refresh(); });
  map.on("sourcedata", (event) => { if (event.sourceId === "shadows") schedule(); });
  return {
    setEnabled(on) {
      enabled = on;
      map.setLayoutProperty("shadows", "visibility", on ? "visible" : "none");
      if (!on) sun = null;
      refresh();
    },
    update(value) { sun = value; refresh(); },
  };
}
