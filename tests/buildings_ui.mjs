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
const listeners = {};
globalThis.document = { getElementById: get, createElement: () => new Element(), hidden: false,
  addEventListener: (event, fn) => { (listeners[event] ||= []).push(fn); } };
const reduced = { matches: false, addEventListener: (_, fn) => { reduced.change = fn; } };
globalThis.window = { matchMedia: () => reduced };
let frameId = 0;
const frames = new Map();
globalThis.requestAnimationFrame = (fn) => { frames.set(++frameId, fn); return frameId; };
globalThis.cancelAnimationFrame = (id) => frames.delete(id);
function frame(time = 0) {
  const pending = [...frames.values()]; frames.clear();
  for (const fn of pending) fn(time);
}
const { initBuildings, wallExposure } = await import(pathToFileURL(folder + "/buildings.js"));
const { showBuildingFacts, clearBuildingCard, refreshFacade, openBuildingSun } = await import(pathToFileURL(folder + "/building-card.js"));
// Check the actual bundled conversion, whose azimuth convention differs from compass bearings.
const { Or: sphericalToCartesian } = await import(pathToFileURL(process.cwd() + "/src/ask_hdb/api/static/vendor/maplibre/maplibre-gl-shared.mjs"));
for (const row of fixture.exposures) assert.ok(Math.abs(wallExposure(...row.args) - row.value) < 1e-10);

class MapStub {
  constructor() { this.layers = {}; this.states = {}; this.sources = {}; this.pitch = 0; this.events = {}; this.eases = []; this.light = { anchor: "viewport", intensity: .4 }; }
  addSource(k, v) { this.sources[k] = { ...v, setData(data) { this.data = data; } }; }
  getSource(k) { return this.sources[k]; }
  isSourceLoaded() { return true; }
  getZoom() { return 16; }
  getBounds() { return { getWest: () => 103.7, getEast: () => 103.9, getSouth: () => 1.2, getNorth: () => 1.4 }; }
  addLayer(v) { this.layers[v.id] = v; }
  setPaintProperty(k, prop, v) { this.layers[k].paint[prop] = v; }
  setFilter(k, f) { (this.layers[k] ||= { layout: {} }).filter = f; }
  setLayoutProperty(k, prop, v) { (this.layers[k] ||= { layout: {} }).layout[prop] = v; }
  setFeatureState({ id }, v) { this.states[id] = { ...this.states[id], ...v }; }
  setLight(v) { this.light = { ...this.light, ...v }; }
  getLight() { return { ...this.light }; }
  getPitch() { return this.pitch; }
  easeTo(v) { this.eases.push(v); this.pitch = v.pitch; this.emit("pitchend", {}); }
  on(event, layer, fn) { (this.events[event] ||= []).push(fn || layer); }
  async emit(event, value) { await Promise.all((this.events[event] || []).map((fn) => fn(value))); }
}
const response = (data, ok = true) => ({ ok, json: async () => data });
let rejectBuildings = false, rejectDay = false;
let pendingFacade = null, pendingBuildings = null, pendingDays = null, buildingRequests = 0;
globalThis.fetch = async (url) => {
  if (url === "/map/buildings") {
    buildingRequests++;
    if (pendingBuildings) return new Promise((resolve) => { pendingBuildings.resolve = resolve; });
    return response(structuredClone(fixture.buildings), !rejectBuildings);
  }
  if (url.startsWith("/sun/block/")) {
    if (pendingFacade) return new Promise((resolve) => { pendingFacade.resolve = resolve; });
    return response(fixture.facades);
  }
  if (url.startsWith("/sun")) {
    if (pendingDays) return new Promise((resolve) => { pendingDays.push({ url, resolve }); });
    return response(fixture.sun, !rejectDay);
  }
  throw Error("Unexpected request: " + url);
};
get("sun-time").value = "960";
const map = new MapStub(), controller = initBuildings(map);
// Colours selected before geometry finishes loading must survive the toggle.
controller.setMetrics("price", { blk_a: [400000, 5, 80] }, ["get", "price"]);
await get("toggle-3d").onclick();
assert.equal(map.pitch, 60);
assert.equal(get("sun-panel").hidden, false, "the sun bar is visible only in 3D");
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
get("sun-time").oninput(); frame();
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

// Only user pitchend events cross the hysteresis thresholds; auto paths never ease.
rejectBuildings = rejectDay = false;
const auto = new MapStub();
initBuildings(auto);
const gesture = async (pitch) => { auto.pitch = pitch; await auto.emit("pitchend", { originalEvent: {} }); };
await gesture(10); assert.equal(auto.layers.buildings, undefined);
auto.pitch = 30; await auto.emit("pitchend", {}); assert.equal(auto.layers.buildings, undefined);
pendingBuildings = {};
const firstTilt = gesture(11), count = buildingRequests;
await gesture(20); assert.equal(buildingRequests, count, "deduplicate an in-flight enable");
pendingBuildings.resolve(response(structuredClone(fixture.buildings))); pendingBuildings = null;
await firstTilt;
assert.equal(auto.layers.buildings.layout.visibility, "visible"); assert.equal(auto.eases.length, 0);
assert.equal(auto.pitch, 20);
await gesture(3); assert.equal(auto.layers.buildings.layout.visibility, "visible");
await gesture(2.9); assert.equal(auto.layers.buildings.layout.visibility, "none");
assert.equal(auto.pitch, 2.9);
assert.equal(get("sun-panel").hidden, true);
assert.equal(auto.eases.length, 0);
await get("toggle-3d").onclick(); assert.equal(auto.pitch, 60, "manual override works below auto threshold");
assert.equal(get("sun-panel").hidden, false);
await get("toggle-3d").onclick(); assert.equal(auto.pitch, 2.9);
auto.pitch = 20;
await get("toggle-3d").onclick(); await get("toggle-3d").onclick();
assert.equal(auto.pitch, 20); assert.equal(auto.layers.buildings.layout.visibility, "none", "oldPitch above threshold cannot auto-reenable");
await gesture(11);
await get("toggle-3d").onclick();
assert.equal(auto.pitch, 20, "automatic paths never overwrite the saved manual pitch");

const levelled = new MapStub(); initBuildings(levelled); pendingBuildings = {}; levelled.pitch = 20;
const delayedTilt = levelled.emit("pitchend", { originalEvent: {} });
levelled.pitch = 0; await levelled.emit("pitchend", { originalEvent: {} });
pendingBuildings.resolve(response(structuredClone(fixture.buildings))); pendingBuildings = null; await delayedTilt;
assert.equal(levelled.layers.buildings.layout.visibility, "none", "levelling during a load cancels its enable");
assert.equal(levelled.eases.length, 0);
pendingDays = [];
const waitingSun = get("toggle-3d").onclick();
await get("toggle-3d").onclick();
assert.equal(levelled.layers.buildings.layout.visibility, "none", "sun loading does not lock out manual off");
pendingDays[0].resolve(response(fixture.sun)); await waitingSun; pendingDays = null;
assert.equal(levelled.layers.buildings.layout.visibility, "none"); assert.equal(levelled.light.anchor, "viewport");

const failed = new MapStub(); initBuildings(failed); rejectBuildings = true; failed.pitch = 20;
await failed.emit("pitchend", { originalEvent: {} });
const afterFailure = buildingRequests;
await failed.emit("pitchend", { originalEvent: {} });
assert.equal(buildingRequests, afterFailure, "a failed auto load is not retried by tilting");
assert.match(get("building-error").textContent, /unavailable/);
rejectBuildings = false;
await get("toggle-3d").onclick(); assert.equal(failed.layers.buildings.layout.visibility, "visible", "manual retry works");

// Freeze the clock in UTC. The Now button must use Singapore's next calendar day.
const NativeDate = Date;
let nowTime = "2026-03-20T16:07:00Z";
globalThis.Date = class extends NativeDate {
  constructor(...args) { super(...(args.length ? args : [nowTime])); }
};
const { singaporeNow } = await import(pathToFileURL(folder + "/sun-controls.js"));
assert.deepEqual(singaporeNow(), { date: "2026-03-21", minute: 360, down: true });
assert.deepEqual(singaporeNow(new NativeDate("2026-03-20T04:44:00Z")), { date: "2026-03-20", minute: 750, down: false });
assert.deepEqual(singaporeNow(new NativeDate("2026-03-20T15:59:00Z")), { date: "2026-03-20", minute: 1170, down: true });
assert.deepEqual(singaporeNow(new NativeDate("2026-03-20T11:44:00Z")), { date: "2026-03-20", minute: 1170, down: true });
pendingDays = []; get("sun-time").value = "960";
const nowPending = get("sun-now").onclick();
assert.match(pendingDays[0].url, /2026-03-21/);
assert.equal(get("sun-time").value, "960", "wait for the matching date before moving the slider");
pendingDays[0].resolve(response({ ...fixture.sun, date: "2026-03-21" })); await nowPending;
assert.equal(get("sun-date").value, "2026-03-21"); assert.equal(get("sun-time").value, "360");
assert.equal(get("sun-position").textContent, "The sun is down.");
nowTime = "2026-03-21T04:44:00Z";
await get("sun-now").onclick();
assert.equal(pendingDays.length, 1, "Now on the loaded date reuses its geometry");
assert.equal(get("sun-time").value, "750");
assert.equal(get("sun-time-label").textContent, "12:30 (+08:00)");
// A newer manual date wins against a delayed Now response, including its target minute.
get("sun-date").value = "2026-03-19";
const staleNow = get("sun-now").onclick();
get("sun-date").value = "2026-03-22"; get("sun-date").onchange();
pendingDays[2].resolve(response({ ...fixture.sun, date: "2026-03-22" }));
for (let i = 0; i < 8; i++) await Promise.resolve();
get("sun-time").value = "720";
pendingDays[1].resolve(response({ ...fixture.sun, date: "2026-03-21" })); await staleNow;
assert.equal(get("sun-date").value, "2026-03-22"); assert.equal(get("sun-time").value, "720");
pendingDays = null; globalThis.Date = NativeDate;

// Playback advances one quarter hour per 150 ms, with no catch-up and no wrap.
frame(); get("sun-play").onclick(); frame(0); frame(149);
assert.equal(get("sun-time").value, "720"); frame(150); assert.equal(get("sun-time").value, "735");
frame(1000); assert.equal(get("sun-time").value, "750", "a slow tick advances only once");
await failed.emit("move", {}); frame(1150); assert.equal(get("sun-time").value, "765", "panning keeps play running");
get("sun-time").oninput(); frame(1300); frame(1450);
assert.equal(get("sun-time").value, "765"); assert.equal(get("sun-play").attrs["aria-pressed"], "false");
get("sun-play").onclick(); frame(2000);
document.hidden = true; for (const fn of listeners.visibilitychange) fn(); frame(2150);
assert.equal(get("sun-time").value, "765"); document.hidden = false;
get("sun-play").onclick(); frame(3000); get("sun-date").onchange();
for (let i = 0; i < 8; i++) await Promise.resolve();
frame(3150); assert.equal(get("sun-play").attrs["aria-pressed"], "false");
get("sun-play").onclick(); frame(4000); await get("toggle-3d").onclick(); frame(4150);
assert.equal(get("sun-play").attrs["aria-pressed"], "false");
await get("toggle-3d").onclick();
get("sun-time").value = "1155"; get("sun-play").onclick(); frame(5000); frame(5150); frame(5300);
assert.equal(get("sun-time").value, "1170"); assert.equal(get("sun-play").attrs["aria-pressed"], "false");
get("sun-play").onclick(); frame(5450); assert.equal(get("sun-time").value, "1170");
get("sun-time").value = "720"; get("sun-play").onclick(); frame(6000);
reduced.matches = true; reduced.change(); frame(6150);
assert.equal(get("sun-time").value, "720"); assert.equal(get("sun-play").disabled, true);
get("sun-play").onclick(); frame(6300); assert.equal(get("sun-play").attrs["aria-pressed"], "false");
reduced.matches = false; reduced.change(); assert.equal(get("sun-play").disabled, false);
get("sun-time").value = "360"; get("sun-play").onclick(); frame(7000);
for (let step = 1; step <= 54; step++) frame(7000 + step * 150);
assert.equal(get("sun-time").value, "1170"); assert.equal(get("sun-play").attrs["aria-pressed"], "false");
reduced.matches = true;
const still = new MapStub(); initBuildings(still); await get("toggle-3d").onclick();
assert.equal(get("sun-play").disabled, true, "initial reduced-motion preference disables play after loading too");
reduced.matches = false;

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
console.log("Offline tilt, Singapore clock, playback, sunlight parity, metric colours and stale responses passed.");
