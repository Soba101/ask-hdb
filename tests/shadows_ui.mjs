// Pure geometry and a deterministic frame/worker stub. No browser or network.
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
const { shadowOffset, shadowPolygons, shadowCollection, initShadows } = await import(pathToFileURL(process.argv[2] + "/shadows.js"));
const close = (a, b) => assert.ok(Math.abs(a - b) < 1e-10, `${a} != ${b}`);
const ring = [[0, 0], [.0001, 0], [.0001, .0001], [0, .0001], [0, 0]];
const feature = { type: "Feature", properties: { block_id: "block_test", height_m: 30 },
  geometry: { type: "Polygon", coordinates: [ring] } };
const sun = { azimuth: 90, altitude: 45 };
const shadow = shadowPolygons(feature, sun)[0].geometry.coordinates[0];
// East sun: a 30 m westward sweep of the whole square, with a closed hull.
assert.equal(shadow.length, 5);
close(Math.min(...shadow.map((p) => p[0])), -30 / 111320);
close(Math.max(...shadow.map((p) => p[0])), .0001);
close(Math.min(...shadow.map((p) => p[1])), 0);
close(Math.max(...shadow.map((p) => p[1])), .0001);
assert.deepEqual(shadow[0], shadow.at(-1));
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
assert.ok(Math.max(...separate[0].geometry.coordinates[0].map((p) => p[0])) < .001);
assert.ok(Math.min(...separate[1].geometry.coordinates[0].map((p) => p[0])) > .99);
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
  addLayer(layer, before) { assert.equal(before, "blocks"); assert.equal(layer.type, "fill"); assert.equal(layer.minzoom, 15); },
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
console.log("Offline shadow direction, hulls, limits, viewport, frame batching and worker backpressure passed.");
