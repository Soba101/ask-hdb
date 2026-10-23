import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { get, folder, response, deferred, tick, point, MapStub, radiusButtons } from "./ui_dom.mjs";
const { initCardMap } = await import(pathToFileURL(folder + "/card-map.js"));
const map = new MapStub(), controls = initCardMap(map);
const schools = [{ id: "school_a", kind: "primary_school", label: "School", lat: 1.31, lng: 103.8, band: "within 1 km" }];
let pending;
const calls = [];
const counts = { counts: { blocks: 10, mrt_lrt: 2, primary_schools: 3, bto_sites: 1 }, limits: ["Straight-line, not MOE's measurement."] };
globalThis.fetch = async (url) => {
  assert.ok(url.startsWith("/around/"), "radius uses only the existing counts route");
  calls.push(url); return pending ? pending.promise : response(counts);
};
const radius = (km) => radiusButtons().find((b) => Number(b.dataset.km) === km);
let stamp = controls.select(point);
controls.schools(point, schools, stamp);
assert.deepEqual(map.rings.map(({ km, dash }) => ({ km, dash })), [{ km: 2, dash: true }, { km: 1, dash: false }]);
assert.equal(map.highlights[0].role, "origin"); assert.equal(map.highlights[1].id, schools[0].id);
assert.ok(map.fits.every((fit) => fit === false)); assert.equal(calls.length, 0);
get("radius-fit").onclick(); assert.equal(map.fits.at(-1), true); assert.equal(calls.length, 0);
controls.chatHighlight(); map.highlight([{ id: "chat" }]);
assert.equal(map.rings.length, 0);
controls.schools(point, schools, stamp);
assert.equal(map.rings.length, 0); assert.equal(map.highlights[0].id, "chat");
stamp = controls.select(point);
const next = { ...point, id: "blk_b" };
controls.select(next); controls.schools(point, schools, stamp);
assert.equal(map.rings.length, 0, "an old selection never gets rings");
stamp = controls.select(point); controls.schools(point, schools, stamp);
await radius(0.5).onclick();
assert.equal(map.rings.length, 1); assert.equal(map.rings[0].km, 0.5);
assert.equal(map.highlights.length, 0); assert.equal(map.fits.at(-1), true);
assert.match(get("radius-counts").textContent, /500 m.*10 blocks, 2 MRT\/LRT, 3 primary schools, 1 BTO sites/);
assert.equal(get("radius-limits").textContent, counts.limits[0]);
await controls.nearby(); assert.equal(calls.length, 1, "a first-open section reuses explicit radius counts");
stamp = controls.select(next); controls.schools(next, schools, stamp);
assert.equal(map.rings.length, 1); assert.equal(map.rings[0].km, 0.5);
assert.equal(map.fits.at(-1), false); assert.equal(calls.length, 1, "selection doesn't eagerly request counts");
await controls.nearby(); await controls.nearby(); assert.equal(calls.length, 2);
// Explicit Off persists too and suppresses late automatic rings.
await radius(0).onclick(); stamp = controls.select(point); controls.schools(point, schools, stamp);
assert.equal(map.rings.length, 0);
assert.equal(radius(0).getAttribute("aria-pressed"), "true");
// A stale count response cannot repaint a new place or a switched-off radius.
pending = deferred(); const late = radius(1).onclick(); await tick();
await radius(0).onclick(); pending.resolve(response(counts)); await late; pending = null;
assert.equal(get("radius-counts").textContent, ""); assert.equal(get("radius-limits").textContent, "");
pending = deferred(); const otherLate = radius(2).onclick(); await tick();
controls.select(next); pending.resolve(response(counts)); await otherLate; pending = null;
assert.equal(get("radius-counts").textContent, "");
controls.select(null); assert.equal(map.rings.length, 0);
// Contract IDs exist exactly once in the actual page; the removed rings button stays removed.
for (const id of ["card", "card-close", "card-title", "card-facts", "card-limits", "card-actions", "schools", "schools-list",
  "schools-summary", "schools-limits", "radius-counts", "points", "toggle-3d", "sun-panel", "sun-date", "sun-time", "sun-time-label",
  "sun-position", "building-error", "card-buildings", "card-sun", "budget", "flat-type"]) get(id);
assert.equal(get("card-close").getAttribute("aria-label"), "Close the info card");
assert.equal(get("selected-clear").getAttribute("aria-label"), "Stop asking about this place");
assert.equal(get("toggle-3d").parentNode.tagName, "details");
assert.equal(get("toggle-3d").parentNode.open, false);
console.log("Default rings, chat precedence, persistent radius choices and stale counts passed.");
