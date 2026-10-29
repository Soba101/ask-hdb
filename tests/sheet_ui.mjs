// Exercise real card callbacks and real sheet events without a browser or remote requests.
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { all, get, folder, fire, point, MapStub, response } from "./ui_dom.mjs";
import { viewport, sheetHeight } from "./sheet_dom.mjs";
const view = viewport(375);
const { initSheet } = await import(pathToFileURL(folder + "/sheet.js"));
const { initCard } = await import(pathToFileURL(folder + "/card.js"));
let chats = 0;
const sheet = initSheet({ chat: () => { chats++; } });
const paddings = [], map = new MapStub();
map.setPadding = (value) => { paddings.push(value); };
sheet.setMap(map);
const handle = get("sheet-handle"), side = get("side"), content = get("sheet-content");
const state = () => side.dataset.snap;
const key = (key, target = handle) => fire(target, "keydown", { key });
const tap = (target) => {
  fire(target, "pointerdown", { clientY: 400 });
  fire(target, "pointerup", { clientY: 400 }); fire(target, "click");
};
const drag = (distance, target = handle) => {
  const before = paddings.length;
  fire(target, "pointerdown", { clientY: 600 });
  fire(target, "pointermove", { clientY: 600 - distance });
  assert.equal(paddings.length, before, "drag frames must not update map padding");
  fire(target, "pointerup", { clientY: 600 - distance });
  fire(target, "click"); // Browsers may synthesize a click after a drag.
};
assert.equal(side.getAttribute("role"), "region");
assert.equal(side.getAttribute("aria-label"), "Results");
assert.equal(state(), "peek"); assert.equal(sheetHeight(), 112);
assert.equal(content.inert, true);
assert.equal(get("peek-hint").textContent, "Ask about a flat, a grant or a place");
assert.equal(get("log").getAttribute("role"), "log");
assert.equal(get("log").getAttribute("aria-live"), "polite");
assert.equal(get("card-summary").getAttribute("aria-live"), "polite");
assert.equal(all().filter((node) => node.getAttribute("aria-live") === "polite").length, 2);
assert.match(handle.getAttribute("aria-label"), /Results, peek.*expand/);
// Below threshold remains a tap; exactly the threshold starts dragging.
fire(handle, "pointerdown", { clientY: 400 });
fire(handle, "pointermove", { clientY: 393 });
assert.equal(sheetHeight(), 112); assert.equal(handle.hasPointerCapture(1), true);
fire(handle, "pointerup", { clientY: 393 }); fire(handle, "click");
assert.equal(state(), "half"); assert.equal(document.activeElement, get("tab-chat"));
assert.equal(content.inert, false);
assert.match(handle.getAttribute("aria-label"), /half height/);
key("Escape"); drag(8); assert.equal(state(), "peek");
drag(140); assert.equal(state(), "peek", "nearest point below the midpoint");
drag(150); assert.equal(state(), "half"); assert.equal(sheetHeight(), 400);
drag(169); assert.equal(state(), "full"); assert.equal(sheetHeight(), 720, "full stops below the search bar (bottom 72) so the chat input stays visible");
assert.match(handle.getAttribute("aria-label"), /full height.*collapse/);
drag(-150); assert.equal(state(), "full", "distance determines snap, with no velocity bias");
drag(-180); assert.equal(state(), "half");
fire(handle, "pointerdown", { clientY: 600 });
fire(handle, "pointermove", { clientY: 350 });
fire(handle, "pointercancel", { clientY: 350 });
assert.equal(state(), "half", "cancel returns to the starting snap");
// Header drags work, while its buttons preserve tap clicks below threshold.
drag(180, get("sheet-header")); assert.equal(state(), "full");
tap(handle); assert.equal(state(), "peek", "handle wraps from full to peek");
for (const [input, expected] of [["ArrowUp", "half"], ["ArrowUp", "full"], ["ArrowUp", "full"],
  ["ArrowDown", "half"], ["Enter", "full"], [" ", "peek"], ["ArrowDown", "peek"]]) {
  assert.equal(key(input).defaultPrevented, true); assert.equal(state(), expected);
}
key("Enter"); key("Enter");
key("Escape", get("tab-evidence")); assert.equal(state(), "half");
key("Escape", get("tab-evidence")); key("Escape"); assert.equal(state(), "peek");
assert.equal(fire(get("map"), "keydown", { key: "Escape" }).defaultPrevented, false);
// Content and the map never capture a drag.
for (const target of [get("log"), get("map")]) {
  fire(target, "pointerdown", { clientY: 500 }); fire(target, "pointermove", { clientY: 100 });
  fire(target, "pointerup", { clientY: 100 }); assert.equal(state(), "peek");
}
get("question").focus(); get("tab-evidence").focus();
assert.equal(document.activeElement, get("question"), "inert content refuses focus");
fire(side, "pointerdown"); handle.focus(); fire(side, "pointerup");
assert.equal(state(), "peek", "a press focusing the handle leaves the click to step it");
get("question").focus(); handle.focus();
assert.equal(state(), "half", "Tab from the search bar into the peek area raises the sheet");
key("Escape", get("question")); assert.equal(state(), "peek");
assert.equal(key("Escape", get("question")).defaultPrevented, false, "Escape at peek is not prevented");
assert.equal(key("Escape").defaultPrevented, false);
// A tap on a child of a header button still clicks that button.
const child = document.createElement("span"); get("card-close").append(child);
let clicks = 0; get("card-close").addEventListener("click", () => { clicks++; });
fire(child, "pointerdown", { clientY: 400 }); fire(child, "pointermove", { clientY: 300 });
fire(child, "pointerup", { clientY: 300 }); fire(child, "click");
assert.equal(clicks, 1); assert.equal(state(), "peek"); child.remove();
key("Escape"); fire(get("question"), "click");
assert.equal(chats, 1); assert.equal(state(), "full");
assert.equal(document.activeElement, get("question"));
// Real selection, section and close handlers notify the sheet without stealing focus.
globalThis.fetch = async (url) => {
  if (url.startsWith("/card/")) return response({ facts: ["Lease started: 1980"], limits: ["Source limits"],
    source: "https://example.test/card", as_of: "2026-10" });
  if (url.startsWith("/schools/")) return response({ schools: [], limits: ["School limits"] });
  throw Error("Unexpected request " + url);
};
const card = initCard({ mapLayer: map, metrics: () => ({ flat: "4 ROOM", data: null }), ask() {},
  onSelect: sheet.select, onSection: sheet.section });
content.scrollTop = 530; // the chat log left the sheet scrolled down
await card.select(point);
assert.equal(state(), "peek"); assert.equal(get("peek-hint").hidden, true);
assert.equal(content.scrollTop, 0, "a selected place opens at its summary");
assert.equal(get("card-summary").hidden, false);
assert.equal(document.activeElement, get("question"));
assert.ok(map.fits.every((fit) => !fit)); assert.equal(map.flies.length, 0);
const prices = get("card-sections").children.find((node) => node.textContent === "Prices");
await prices.onclick(); assert.equal(state(), "half");
key("Escape"); await prices.onclick(); await prices.onclick();
assert.equal(state(), "half", "reopening a loaded section raises the sheet too");
tap(get("card-close")); assert.equal(state(), "peek");
assert.equal(get("peek-hint").hidden, false); assert.equal(get("card-summary").hidden, true);
assert.equal(content.inert, true);
assert.equal(chats, 2, "closing the card returns to Chat");
sheet.answer(); assert.equal(state(), "half"); assert.equal(chats, 3);
assert.equal(document.activeElement, get("question"));
assert.ok(get("side").textContent.includes("Source limits"));
assert.ok(get("side").textContent.includes("https://example.test/card"));
assert.ok(get("side").textContent.includes("2026-10"));
assert.ok(get("sheet-notes").contains(get("sun-panel-limits")));
assert.ok(!get("sun-panel").contains(get("sun-panel-limits")));
// Run the existing 3D controller against the moved sun panel, with local geometry only.
const { initBuildings } = await import(pathToFileURL(folder + "/buildings.js"));
document.addEventListener = () => {};
globalThis.requestAnimationFrame = () => 1;
globalThis.cancelAnimationFrame = () => {};
globalThis.fetch = async (url) => {
  if (url === "/map/buildings") return response({ type: "FeatureCollection", features: [] });
  if (url === "/sun") return response({ date: "2026-03-20",
    positions: Array.from({ length: 97 }, () => ({ azimuth: 90, altitude: 45 })) });
  throw Error("Unexpected request " + url);
};
const buildingMap = { on() {}, addSource() {}, addLayer() {}, setPaintProperty() {},
  setFeatureState() {}, setLight() {}, setLayoutProperty() {}, setFilter() {}, easeTo() {},
  getLight: () => ({}), getPitch: () => 0 };
initBuildings(buildingMap);
assert.equal(get("sun-panel").hidden, true);
assert.equal(get("sun-panel").parentNode.id, "sun-bar");
await get("toggle-3d").onclick();
assert.equal(get("toggle-3d").getAttribute("aria-pressed"), "true");
assert.equal(get("sun-panel").hidden, false);
assert.ok(!get("sun-panel").contains(get("sun-panel-limits")));
await get("toggle-3d").onclick();
assert.equal(get("sun-panel").hidden, true);
assert.equal(get("toggle-3d").getAttribute("aria-pressed"), "false");
// Keyboard inset accounts for viewport panning as well as shrinking.
window.visualViewport.height = 500; window.visualViewport.offsetTop = 20; view.keyboard();
assert.equal(get("app").style.getPropertyValue("--kb"), "280px");
assert.equal(sheetHeight(), 400); assert.equal(side.dataset.snap, "half");
assert.equal(sheet.padding(60), 60, "setPadding already applies the sheet height");
window.visualViewport.height = 800; window.visualViewport.offsetTop = 0; view.keyboard();
assert.equal(get("app").style.getPropertyValue("--kb"), "0px");
window.innerHeight = 1000; window.visualViewport.height = 1000; view.resize();
assert.equal(sheetHeight(), 500); assert.equal(paddings.at(-1).bottom, 500);
view.mobile.matches = false; view.mobile.change();
assert.equal(sheet.padding(60), 60); assert.equal(paddings.at(-1).bottom, 0);
const count = paddings.length;
sheet.answer(); sheet.section(); sheet.select(point); view.keyboard(); view.resize();
assert.equal(paddings.length, count, "desktop hooks are inert");
console.log("Sheet snaps, tap threshold, keyboard, selection, focus, inset and map padding passed.");
