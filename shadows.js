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
// Douglas-Peucker on a closed ring, in metres. Display only: 1 m is about a pixel at zoom 17.
function simplify(ring, tolerance = 1) {
  const scale = Math.cos(radians(ring[0][1])) * 111320, pts = ring.map(([x, y]) => [x * scale, y * 110540]);
  const keep = new Uint8Array(ring.length), last = ring.length - 1;
  let far = 0, farthest = -1;
  for (let i = 1; i < last; i++) {
    const d = Math.hypot(pts[i][0] - pts[0][0], pts[i][1] - pts[0][1]);
    if (d > farthest) { farthest = d; far = i; }
  }
  keep[0] = keep[last] = keep[far] = 1;
  const stack = [[0, far], [far, last]];
  while (stack.length) {
    const [a, b] = stack.pop(), [ax, ay] = pts[a], dx = pts[b][0] - ax, dy = pts[b][1] - ay, length = Math.hypot(dx, dy) || 1;
    let worst = -1, at = -1;
    for (let i = a + 1; i < b; i++) {
      const d = Math.abs(dx * (pts[i][1] - ay) - dy * (pts[i][0] - ax)) / length;
      if (d > worst) { worst = d; at = i; }
    }
    if (worst > tolerance) { keep[at] = 1; stack.push([a, at], [at, b]); }
  }
  const out = ring.filter((_, i) => keep[i]);
  return out.length >= 4 ? out : ring;
}
const oriented = new WeakMap(); // footprints never change, so simplify and orient each part once
function rings(polygon) {
  if (!oriented.has(polygon)) oriented.set(polygon, polygon.map((ring, i) => {
    const r = simplify(ring);
    return (signedArea(r) > 0) === (i === 0) ? r : [...r].reverse();
  }));
  return oriented.get(polygon);
}
// An extruded flat roof shades P plus the sweep of each wall that faces away from the sun.
// From any shaded point, a step back toward the sun enters P through one of those walls.
// Consecutive facing walls are monotone across the shadow direction, so each run sweeps into one simple band.
function sweep(polygon, offset) {
  const footprint = rings(polygon), bands = [];
  for (const ring of footprint) {
    const n = ring.length - 1;
    // Outward normal of a CCW outer ring (and of a CW hole) is (dy, -dx). Metre scales are a positive factor.
    const faces = Array.from({ length: n }, (_, i) =>
      (ring[i + 1][1] - ring[i][1]) * offset[0] - (ring[i + 1][0] - ring[i][0]) * offset[1] > 0);
    const start = faces.findIndex((f, i) => f && !faces[(i + n - 1) % n]);
    if (start < 0) continue; // all walls face the sun, or none do (degenerate)
    for (let k = 0; k < n; k++) {
      const i = (start + k) % n;
      if (!faces[i] || (k > 0 && faces[(i + n - 1) % n])) continue;
      const chain = [ring[i]];
      for (let j = i; faces[j % n] && chain.length <= n; j++) chain.push(ring[(j + 1) % n]);
      const moved = chain.map(([x, y]) => [x + offset[0], y + offset[1]]).reverse();
      bands.push([[...chain, ...moved, chain[0]]]);
    }
  }
  return [footprint, ...bands];
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
