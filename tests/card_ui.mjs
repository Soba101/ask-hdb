// Real page structure, fake endpoint responses: no browser, tiles or models.
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { all, get, folder, response, deferred, tick, point, MapStub } from "./ui_dom.mjs";
const { initCard } = await import(pathToFileURL(folder + "/card.js"));
const facts = ["Town: Bedok", "Lease started: 1980", "Sales in the 12 months to 2026-10: 6",
  "4 Room: 5 sales, median $402,000", "3 Room: 1 sale (too few for a median)",
  "Nearest primary school: A School, 0.12 km", "Nearest MRT: X, 1.23 km"];
const data = { facts, floors: 12, height_source: "property_info", facing_label: "East / West <img src=x>",
  limits: ["Straight-line distances, not walking or travel times.", "Not a valuation. Check MOE with OneMap."],
  storey_prices: [{ label: "01–03", median_price: 401000, sales: 7 }],
  storey_prices_as_of: "2026-10", storey_prices_limits: "All flat types pooled. No unit-level price or facing; not a forecast.",
  source: "https://example.test/resales", as_of: "2026-10-01" };
const schoolData = { schools: [{ id: "school_a", label: "A <script>School</script>", kind: "primary_school",
  km: 0.12, band: "within 1 km", lat: 1.301, lng: 103.8 },
  { id: "school_b", label: "B School", kind: "primary_school", km: 2.1, band: "borderline", lat: 1.32, lng: 103.8 }],
  limits: ["Approximate bands; not MOE's measurement. Being nearby does not guarantee a place."] };
const sun = { date: "2026-03-20", facades: [{ label: "East", hours: 6, peak_time: "09:00" }], limits: "No shade from blocks or clouds." };
let metric = { flat: "4 ROOM", data: { blocks: { blk_a: [405000, 8, 53] }, window_months: 24,
  limits: ["Recorded resales; size and condition differ.", "Remaining lease rounded down."], as_of: "2026-10" } };
let pendingSchool, pendingCard, pendingSun;
const calls = [];
globalThis.fetch = async (url) => {
  calls.push(url);
  if (url.startsWith("/card/")) return pendingCard ? pendingCard.promise : response(structuredClone(data));
  if (url.startsWith("/schools/")) return pendingSchool ? pendingSchool.promise : response(schoolData);
  if (url.startsWith("/sun/block/")) return pendingSun ? pendingSun.promise : response(sun);
  throw Error("Unexpected request " + url);
};
const map = new MapStub(), questions = [];
const card = initCard({ mapLayer: map, metrics: () => metric, ask: (question) => questions.push(question) });
const chip = (label) => get("card-sections").children.find((e) => e.textContent === label);
const count = (prefix) => calls.filter((url) => url.startsWith(prefix)).length;
const text = () => get("card").textContent;
const openCount = () => get("card-sections").children.filter((e) => e.getAttribute("aria-expanded") === "true").length;
await card.select(point); await tick();
assert.equal(openCount(), 0);
for (const b of get("card-sections").children) assert.equal(get(b.getAttribute("aria-controls")).hidden, true);
assert.equal(count("/card/"), 1); assert.equal(count("/schools/"), 1); assert.equal(count("/sun/"), 0);
assert.equal(map.rings.length, 2); assert.ok(map.fits.every((fit) => !fit));
assert.match(get("card-facts").textContent, /405,000.*median|median.*405,000/);
assert.match(get("card-facts").textContent, /53 years/);
assert.match(get("card-facts").textContent, /East \/ West <img src=x>/);
assert.ok(!get("card").getAttribute("aria-live"));
assert.equal(get("card-summary").getAttribute("aria-live"), "polite");
assert.equal(all(get("card")).filter((e) => e.getAttribute("aria-live")).length, 1);
assert.equal(all(get("card")).filter((e) => ["img", "script"].includes(e.tagName)).length, 0);
await chip("Prices").onclick(); assert.equal(openCount(), 1); assert.equal(get("card-prices").hidden, false);
await chip("Lease").onclick(); assert.equal(openCount(), 1); assert.equal(get("card-prices").hidden, true);
await chip("Lease").onclick(); assert.equal(openCount(), 0);
await chip("Schools").onclick(); await chip("Schools").onclick(); await chip("Schools").onclick();
assert.equal(count("/schools/"), 1, "default rings and first-open list share one request");
assert.match(get("schools-summary").textContent, /2 km: 1 \(\+1 borderline\)/);
assert.match(get("schools-list").textContent, /0.12 km/);
get("schools-list").children[0].children[0].onclick(); assert.equal(map.flies.length, 1);
await chip("Sun and facing").onclick(); await chip("Prices").onclick(); await chip("Sun and facing").onclick();
assert.equal(count("/sun/"), 1, "sun loads only on first open");
assert.equal(count("/card/"), 1, "sections reuse the summary response");
// Every old fact and qualifier remains reachable in the DOM, even in a closed disclosure.
for (const value of [...facts, ...data.limits, data.storey_prices_limits, data.storey_prices_as_of,
  data.source, data.as_of, ...metric.data.limits, ...schoolData.limits, sun.limits,
  "12 floors", "HDB property information", "Approximate block facing:", "(not per unit).",
  "Storeys 01–03: $401,000 median · 7 sales", "East facade: 6 hours · peak 09:00", "(+08:00)",
  "last 24 months", "from 8 sales", "2.10 km", "borderline"]) assert.ok(text().includes(value), value);
for (const id of ["card-limits", "metrics-limits", "building-limits", "sun-limits", "schools-limits", "radius-limits"])
  assert.ok(get("card-about").contains(get(id)), id + " belongs in the shared disclosure");
get("card-actions").children[0].onclick(); assert.equal(questions[0], "What are the 3 nearest primary schools to this block?");
metric = { flat: "5 ROOM", data: null }; card.refreshMetrics();
assert.ok(!get("card-facts").textContent.includes("405,000"));
assert.ok(get("card-facts").textContent.includes("Lease started: 1980"));
assert.ok(!get("card-facts").textContent.includes("53 years"));
metric.data = { blocks: { blk_a: [null, 2, 0] }, window_months: 24, limits: [] }; card.refreshMetrics();
assert.match(get("card-facts").textContent, /about 0 years/);
assert.ok(!get("card-facts").textContent.includes("median"));
assert.match(get("metric-prices").textContent, /too few for a median/);
// First-open school requests for non-block cards stay lazy and discard late results.
pendingSchool = deferred();
await card.select({ ...point, kind: "mrt", id: "mrt_a" });
const beforeSchools = count("/schools/");
const lateSchool = chip("Schools").onclick(); await tick();
assert.equal(count("/schools/"), beforeSchools + 1);
await chip("Nearby").onclick(); const reopen = chip("Schools").onclick();
assert.equal(count("/schools/"), beforeSchools + 1, "pending first open is deduplicated");
await card.select({ ...point, kind: "lrt", id: "lrt_b" });
pendingSchool.resolve(response(schoolData)); pendingSchool = null;
await Promise.all([lateSchool, reopen]);
assert.equal(get("schools-list").children.length, 0); assert.equal(get("schools-limits").textContent, "");
// Late sun and card responses cannot fill a newer selection, including after closing.
await card.select(point); pendingSun = deferred();
const lateSun = chip("Sun and facing").onclick(); await tick();
await card.select({ ...point, kind: "primary_school", id: "school_new" });
pendingSun.resolve(response(sun)); pendingSun = null; await lateSun;
assert.equal(get("card-sun").textContent, ""); assert.equal(get("sun-limits").textContent, "");
pendingCard = deferred(); const lateCard = card.select(point); await tick();
get("card-close").onclick(); pendingCard.resolve(response(data)); pendingCard = null; await lateCard;
assert.equal(get("card").hidden, true); assert.equal(get("card-facts").textContent, "");
// Other place types retain their first two server facts exactly, without interpreting numbers.
for (const kind of ["bto", "mrt", "lrt", "primary_school"]) {
  await card.select({ ...point, kind });
  const headlines = get("card-facts").children;
  assert.equal(headlines.length, 2);
  facts.slice(0, 2).forEach((fact, i) => assert.ok(headlines[i].textContent.startsWith(fact)));
  for (const fact of facts) assert.ok(text().includes(fact));
}
console.log("Card disclosures, lazy loads, stale responses, literal text, figures and limits passed.");
