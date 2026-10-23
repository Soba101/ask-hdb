// Offline controller checks. This deliberately makes no tile, model or browser requests.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";

const folder = process.argv[2];
const fixture = JSON.parse(await readFile(folder + "/fixture.json", "utf8"));
class Element {
  constructor() { this.value = ""; this.children = []; this.attrs = {}; this.hidden = false; this.classList = { toggle() {} }; }
  setAttribute(k, v) { this.attrs[k] = v; }
  appendChild(v) { this.children.push(v); }
  replaceChildren() { this.children = []; }
}
const elements = new Map();
const get = (id) => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
globalThis.document = { getElementById: get, createElement: () => new Element() };
globalThis.requestAnimationFrame = (fn) => { fn(); return 1; };
globalThis.cancelAnimationFrame = () => {};
const { initBuildings, wallExposure } = await import(pathToFileURL(folder + "/buildings.js"));
const { showBuildingFacts, clearBuildingCard, refreshFacade, openBuildingSun } = await import(pathToFileURL(folder + "/building-card.js"));
// Check the actual bundled conversion, whose azimuth convention differs from compass bearings.
const { Or: sphericalToCartesian } = await import(pathToFileURL(process.cwd() + "/src/ask_hdb/api/static/vendor/maplibre/maplibre-gl-shared.mjs"));
for (const row of fixture.exposures) assert.ok(Math.abs(wallExposure(...row.args) - row.value) < 1e-10);

class MapStub {
  constructor() { this.layers = {}; this.states = {}; this.sources = {}; this.pitch = 0; this.light = { anchor: "viewport", intensity: .4 }; }
  addSource(k, v) { this.sources[k] = v; }
  addLayer(v) { this.layers[v.id] = v; }
  setPaintProperty(k, prop, v) { this.layers[k].paint[prop] = v; }
  setFilter(k, f) { (this.layers[k] ||= { layout: {} }).filter = f; }
  setLayoutProperty(k, prop, v) { (this.layers[k] ||= { layout: {} }).layout[prop] = v; }
  setFeatureState({ id }, v) { this.states[id] = { ...this.states[id], ...v }; }
  setLight(v) { this.light = { ...this.light, ...v }; }
  getLight() { return { ...this.light }; }
  getPitch() { return this.pitch; }
  easeTo(v) { this.pitch = v.pitch; }
  on() {}
}
const response = (data, ok = true) => ({ ok, json: async () => data });
let rejectBuildings = false, rejectDay = false;
let pendingFacade = null;
globalThis.fetch = async (url) => {
  if (url === "/map/buildings") return response(structuredClone(fixture.buildings), !rejectBuildings);
  if (url.startsWith("/sun/block/")) {
    if (pendingFacade) return new Promise((resolve) => { pendingFacade.resolve = resolve; });
    return response(fixture.facades);
  }
  if (url.startsWith("/sun")) return response(fixture.sun, !rejectDay);
  throw Error("Unexpected request: " + url);
};
get("sun-time").value = "960";
const map = new MapStub(), controller = initBuildings(map);
// Colours selected before geometry finishes loading must survive the toggle.
controller.setMetrics("price", { blk_a: [400000, 5, 80] }, ["get", "price"]);
await get("toggle-3d").onclick();
assert.equal(map.pitch, 60);
assert.ok(map.layers.blocks.filter, "blocks with an outline are hidden, others stay as points");
assert.equal(map.layers.buildings.layout.visibility, "visible");
assert.equal(map.layers.buildings.paint["fill-extrusion-height"][1], "height_m");
assert.equal(map.states.blk_a.price, 400000);
assert.equal(map.light.anchor, "map");
assert.equal(map.light.position[1], (fixture.sun.positions[64].azimuth + 180) % 360);
assert.equal(map.light.position[2], 90 - fixture.sun.positions[64].altitude);
const vector = sphericalToCartesian(map.light.position), sun = fixture.sun.positions[64];
const az = sun.azimuth * Math.PI / 180, alt = sun.altitude * Math.PI / 180;
const expected = [1.15 * Math.cos(alt) * Math.sin(az), -1.15 * Math.cos(alt) * Math.cos(az), 1.15 * Math.sin(alt)];
vector.forEach((v, i) => assert.ok(Math.abs(v - expected[i]) < 1e-10));
assert.equal(get("sun-date").value, fixture.sun.date);
assert.ok(!map.states.blk_a.exposure, "exposure is only computed in Type mode");
assert.deepEqual(map.layers.buildings.paint["fill-extrusion-color"], ["coalesce", ["feature-state", "price"], 0]);
controller.setMetrics("lease", { blk_a: [400000, 5, 80] }, ["get", "lease"]);
assert.equal(map.states.blk_a.lease, 80);
controller.setMetrics("type", {}, "#blue");
assert.equal(map.layers.buildings.paint["fill-extrusion-color"][0], "interpolate");
get("sun-time").value = "360";
get("sun-time").oninput();
assert.equal(map.states.blk_a.exposure, 0);
assert.equal(map.light.intensity, 0);
await get("toggle-3d").onclick();
assert.equal(map.pitch, 0);
assert.equal(map.light.anchor, "viewport");
assert.equal(map.light.intensity, .4);
assert.deepEqual(map.light.position, [1.15, 210, 30]);
assert.equal(map.layers.blocks.filter, null);
assert.equal(map.layers.buildings.layout.visibility, "none");
assert.equal(get("sun-panel").hidden, true);

rejectDay = true;
await get("toggle-3d").onclick();
assert.match(get("sun-position").textContent, /valid date/);
assert.equal(get("sun-time").disabled, true);
assert.equal(map.states.blk_a.exposure, 0);
rejectBuildings = true;
const absent = new MapStub();
initBuildings(absent);
await get("toggle-3d").onclick();
assert.equal(absent.pitch, 0);
assert.match(get("building-error").textContent, /unavailable/);

// Strings are text, and late facade responses cannot resurrect a cleared selection.
const point = { id: "blk_a" };
const facts = { floors: 12, height_source: "property_info", facing_label: "<img src=x>",
  storey_prices: [], storey_prices_limits: "Historical only" };
showBuildingFacts(facts, point);
await openBuildingSun(point);
assert.ok(get("card-buildings").children.some((p) => p.textContent.includes("<img src=x>")));
assert.ok(get("card-sun").children.some((p) => p.textContent.includes("Illustrative")));
pendingFacade = {};
get("sun-date").value = "2026-03-21";
const late = refreshFacade();
clearBuildingCard();
pendingFacade.resolve(response(fixture.facades));
await late;
assert.equal(get("card-sun").children.length, 0);
console.log("Offline building controls, sunlight parity, metric colours and stale cards passed.");
