// Pure geometry and a deterministic frame/worker stub. No browser or network.
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
const { shadowOffset, shadowPolygons, shadowCollection, initShadows } = await import(pathToFileURL(process.argv[2] + "/shadows.js"));
const close = (a, b) => assert.ok(Math.abs(a - b) < 1e-10, `${a} != ${b}`);
const ring = [[0, 0], [.0001, 0], [.0001, .0001], [0, .0001], [0, 0]];
const feature = { type: "Feature", properties: { block_id: "block_test", height_m: 30 },
  geometry: { type: "Polygon", coordinates: [ring] } };
const sun = { azimuth: 90, altitude: 45 };
// Even-odd within each polygon (holes), any polygon of the MultiPolygon counts.
const inRing = ([x, y], ring) => ring.slice(1).reduce((inside, b, i) => {
  const a = ring[i];
  return (a[1] > y) !== (b[1] > y) && x < a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]) ? !inside : inside;
}, false);
const shaded = (features, point) => features.some((f) => f.geometry.coordinates.some((rings) =>
  rings.reduce((inside, ring) => inside !== inRing(point, ring), false)));
const m = 1 / 111320; // one metre east at the equator
const shadow = shadowPolygons(feature, sun);
// East sun: a 30 m westward sweep of the whole square, and nothing east of it.
assert.equal(shadow.length, 1);
for (const ring of shadow[0].geometry.coordinates.flat()) assert.deepEqual(ring[0], ring.at(-1));
assert.ok(shaded(shadow, [-29 * m, .00005]) && shaded(shadow, [.00005, .00005]));
assert.ok(!shaded(shadow, [-31 * m, .00005]) && !shaded(shadow, [.00011, .00005]) && !shaded(shadow, [-10 * m, .00011]));
assert.equal(shadow[0].geometry.coordinates.length, 2, "footprint plus the one wall facing away from the sun");
// A U open to the north (clockwise on purpose), 5 m tall, low south sun: the notch stays lit, ground behind the arms is shaded.
const u = [[0, 0], [0, 30], [10, 30], [10, 10], [20, 10], [20, 30], [30, 30], [30, 0], [0, 0]].map(([x, y]) => [x * m, y * m]);
const uFeature = { ...feature, properties: { ...feature.properties, height_m: 5 }, geometry: { type: "Polygon", coordinates: [u] } };
const uShadow = shadowPolygons(uFeature, { azimuth: 180, altitude: 45 });
assert.ok(!shaded(uShadow, [15 * m, 20 * m]), "the notch is lit by the short shadow");
assert.ok(shaded(uShadow, [15 * m, 12 * m]) && shaded(uShadow, [5 * m, 33 * m]) && !shaded(uShadow, [15 * m, 33 * m]));
// Each run of walls facing away from the sun is one band: the U under a south sun has three runs (two arm tops, the notch floor).
assert.equal(uShadow[0].geometry.coordinates.length, 4);
// Simplification: collinear points and a 0.3 m wiggle go, real 3 m steps stay; tiny rings stay whole.
const wiggly = [[0, 0], [10, 0], [20, .3], [30, 0], [40, 0], [40, 20], [37, 20], [37, 23], [0, 23], [0, 0]].map(([x, y]) => [x * m, y * m]);
const wShadow = shadowPolygons({ ...uFeature, geometry: { type: "Polygon", coordinates: [wiggly] } }, { azimuth: 180, altitude: 45 });
assert.equal(wShadow[0].geometry.coordinates[0][0].length, 7, "four bottom points become two; the step stays");
assert.ok(shaded(wShadow, [38.5 * m, 24 * m]) && !shaded(wShadow, [38.5 * m, 26 * m]));
// A gable: two north walls form one run and one simple band, whose area is the swept width times the shadow length.
const gable = [[0, 0], [40, 0], [40, 20], [20, 25], [0, 20], [0, 0]].map(([x, y]) => [x * m, y * m]);
const gShadow = shadowPolygons({ ...uFeature, geometry: { type: "Polygon", coordinates: [gable] } }, { azimuth: 180, altitude: 45 });
assert.equal(gShadow[0].geometry.coordinates.length, 2, "one band for the whole run");
const band = gShadow[0].geometry.coordinates[1][0].map(([x, y]) => [x / m, y * 110540]);
close(Math.abs(band.reduce((sum, p, i) => i ? sum + band[i - 1][0] * p[1] - p[0] * band[i - 1][1] : 0, 0) / 2), 40 * 5);
// A courtyard block: the courtyard is lit except the band behind its sunny wall.
const outer = [[0, 0], [40, 0], [40, 40], [0, 40], [0, 0]].map(([x, y]) => [x * m, y * m]);
const hole = [[10, 10], [10, 30], [30, 30], [30, 10], [10, 10]].map(([x, y]) => [x * m, y * m]);
const ring2 = { ...uFeature, geometry: { type: "Polygon", coordinates: [outer, hole] } };
const ringShadow = shadowPolygons(ring2, { azimuth: 180, altitude: 45 });
assert.ok(shaded(ringShadow, [20 * m, 12 * m]) && !shaded(ringShadow, [20 * m, 20 * m]) && shaded(ringShadow, [5 * m, 20 * m]));
assert.deepEqual(shadowPolygons(feature, { ...sun, altitude: 9.99 }), []);
assert.equal(shadowPolygons(feature, { ...sun, altitude: 10 }).length, 1);
close(shadowOffset(1000, { azimuth: 0, altitude: 10 }, 0)[1], -300 / 110540);
// Compass bearings from sun.py: north, east, south and west; diagonal and longitude scale too.
for (const [azimuth, east, north] of [[0, 0, -30], [90, -30, 0], [180, 0, 30], [270, 30, 0],
  [45, -30 / Math.sqrt(2), -30 / Math.sqrt(2)]]) {
  const offset = shadowOffset(30, { azimuth, altitude: 45 }, 60);
  close(offset[0] * 111320 * Math.cos(Math.PI / 3), east);
  close(offset[1] * 110540, north);
}
const multi = { ...feature, geometry: { type: "MultiPolygon", coordinates: [[ring], [ring.map(([x, y]) => [x + 1, y])]] } };
const separate = shadowPolygons(multi, sun);
assert.equal(separate.length, 2);
assert.ok(Math.max(...separate[0].geometry.coordinates.flat(2).map((p) => p[0])) < .001);
assert.ok(Math.min(...separate[1].geometry.coordinates.flat(2).map((p) => p[0])) > .99);
const view = { west: -.00001, south: -.00001, east: .00001, north: .00001 };
const index = [{ feature, box: [0, 0, .0001, .0001] }];
assert.equal(shadowCollection(index, sun, view, 14.99).features.length, 0);
assert.equal(shadowCollection(Array(700).fill(index[0]), sun, view, 15).features.length, 600);
const shifted = (x) => ({ feature: { ...feature, geometry: { type: "Polygon", coordinates: [ring.map(([a, b]) => [a + x, b])] } },
  box: [x, 0, x + .0001, .0001] });
assert.equal(shadowCollection([shifted(.002)], sun, view, 15).features.length, 1, "include casters on sun side");
assert.equal(shadowCollection([shifted(-.002), shifted(.004)], sun, view, 15).features.length, 0);
let nextId = 0, frames = new Map(), busy = false, writes = [], zoom = 16;
globalThis.requestAnimationFrame = (fn) => { frames.set(++nextId, fn); return nextId; };
const frame = () => { const pending = [...frames.values()]; frames.clear(); pending.forEach((fn) => fn()); };
const events = {}, layouts = {};
const map = {
  addSource(id, source) { assert.equal(id, "shadows"); assert.equal(source.type, "geojson"); },
  addLayer(layer, before) { assert.equal(before, "blocks"); assert.equal(layer.type, "fill-extrusion"); assert.equal(layer.paint["fill-extrusion-height"], 0.1); assert.equal(layer.minzoom, 15); },
  setLayoutProperty(id, prop, value) { layouts[id] = value; },
  getSource() { return { setData(data) { busy = true; writes.push(data); } }; },
  isSourceLoaded() { return !busy; }, getZoom() { return zoom; },
  getBounds() { return { getWest: () => -.01, getEast: () => .01, getSouth: () => -.01, getNorth: () => .01 }; },
  on(event, fn) { events[event] = fn; },
};
const controller = initShadows(map, { features: [feature] });
controller.setEnabled(true); controller.update(sun); controller.update({ ...sun, azimuth: 0 });
assert.equal(writes.length, 0); frame(); assert.equal(writes.length, 1);
assert.deepEqual(writes[0].features, shadowPolygons(feature, { ...sun, azimuth: 0 }), "latest whole time only");
controller.update(sun); events.move(); frame();
assert.equal(writes.length, 1, "skip while the worker still processes the previous frame");
busy = false; events.sourcedata({ sourceId: "shadows" }); frame();
assert.equal(writes.length, 2); assert.deepEqual(writes[1].features, shadowPolygons(feature, sun));
busy = false; zoom = 14; events.move(); frame(); assert.equal(writes.at(-1).features.length, 0);
busy = false; zoom = 16; controller.update(sun); frame(); assert.equal(writes.at(-1).features.length, 1);
controller.setEnabled(false); assert.equal(layouts.shadows, "none"); frame();
assert.equal(writes.at(-1).features.length, 1, "clear waits for the previous collection");
busy = false; events.sourcedata({ sourceId: "shadows" }); frame();
assert.equal(writes.at(-1).features.length, 0);
console.log("Offline shadow direction, exact sweeps, limits, viewport, frame batching and worker backpressure passed.");
