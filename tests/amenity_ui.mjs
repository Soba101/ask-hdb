// Nearest places and the walking route: real page, fake endpoints, no browser or network.
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { all, get, folder, fire, response, deferred, tick, point, MapStub } from "./ui_dom.mjs";
const { initAmenityCard } = await import(pathToFileURL(folder + "/amenity-card.js"));
const map = new MapStub();
let routes = 0;
const amenity = initAmenityCard({ mapLayer: map, onRoute: () => { routes++; } });
const pills = all().filter((e) => e.dataset.type !== undefined);
assert.equal(pills.length, 3);
const items = [{ id: "osm:node/1", name: "<b>FairPrice</b>", ref: null, lat: 1.31, lng: 103.81, km: 0.15 },
  { id: "osm:node/2", name: "Cold Storage", ref: null, lat: 1.32, lng: 103.82, km: 1.2 }];
const requests = [];
let routeReply = { distance_m: 197, duration_s: 142, to: "FairPrice", line: [[103.8, 1.3], [103.81, 1.31]],
  steps: [{ text: "Head East", road: "A", distance_m: 100 }, { text: "Arrive", road: "", distance_m: 0 }],
  source: "Route: OneMap (SLA), walking estimate", limits: ["Walking time is an estimate."] };
globalThis.fetch = async (url) => {
  requests.push(url);
  if (url.startsWith("/nearby/")) return response({ items, source: "OpenStreetMap", as_of: "2026-10-29", limits: ["Straight-line."] });
  if (url.startsWith("/route/")) return response(routeReply, !routeReply.error);
  throw Error("Unexpected request " + url);
};
amenity.select(point);
pills[0].onclick(); await tick(); await tick();
assert.equal(pills[0].getAttribute("aria-pressed"), "true");
assert.ok(requests[0].startsWith("/nearby/block/blk_a?type=supermarket"));
assert.equal(map.markers.length, 2);
const rows = get("amenity-list").children;
assert.equal(rows.length, 2);
assert.ok(rows[0].textContent.includes("<b>FairPrice</b>"), "names are text, never markup");
assert.ok(get("amenity-note").textContent.includes("OpenStreetMap"));
// Walk draws the route, lists the steps and raises the sheet.
const walk = rows[0].children.find((n) => n.tagName === "button");
await walk.onclick(); await tick();
assert.ok(requests.at(-1).includes("to=osm%3Anode%2F1"));
assert.equal(get("route-block").hidden, false);
assert.equal(get("route-steps").children.length, 2);
assert.ok(get("route-summary").textContent.includes("2 min"));
assert.deepEqual(map.line, routeReply.line); assert.equal(routes, 1);
get("route-clear").onclick();
assert.equal(get("route-block").hidden, true); assert.equal(map.line, null);
// An error shows its plain message and draws nothing.
routeReply = { error: "no_credentials", message: "Walking directions need OneMap credentials in .env." };
await walk.onclick(); await tick();
assert.equal(get("amenity-note").textContent, routeReply.message); assert.equal(get("route-block").hidden, true);
// A late route answer cannot draw over a newer selection.
const late = deferred();
routeReply = { ...routeReply, error: undefined };
globalThis.fetch = async (url) => { await late.promise; return response({ ...{ distance_m: 1, duration_s: 60, to: "X", steps: [], limits: [], source: "s" }, line: [[1, 1], [2, 2]] }); };
const pending = walk.onclick();
amenity.select({ ...point, id: "blk_b" });
late.resolve(); await pending; await tick();
assert.equal(get("route-block").hidden, true); assert.equal(map.line, null);
assert.equal(get("amenity-list").children.length, 0); assert.equal(pills[0].getAttribute("aria-pressed"), "false");
console.log("Nearby places, walking route, errors and stale answers passed.");
