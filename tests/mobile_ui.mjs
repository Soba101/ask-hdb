// Real markup with local event stubs: no browser, network, tiles or models.
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { all, get, folder } from "./ui_dom.mjs";
const { initLayers } = await import(pathToFileURL(folder + "/buildings.js"));
const toggle = get("layers-toggle"), panel = get("layers");
const mode = all(panel).find((node) => node.dataset.mode === "type");
for (const node of all()) node.focus = () => { document.activeElement = node; };
panel.querySelector = (selector) => {
  assert.equal(selector, "button");
  return mode;
};
globalThis.fetch = () => { throw Error("Unexpected network request"); };
for (const width of [360, 375, 430, 800, 801]) {
  const handlers = {}, mobile = { matches: width <= 800 };
  mobile.addEventListener = (event, handler) => {
    assert.equal(event, "change");
    mobile.change = handler;
  };
  globalThis.window = { matchMedia: (query) => {
    assert.equal(query, "(max-width: 800px)");
    return mobile;
  } };
  document.addEventListener = (event, handler) => { handlers[event] = handler; };
  document.activeElement = null;
  initLayers();
  const expanded = () => toggle.getAttribute("aria-expanded");
  assert.equal(expanded(), "false", "initial phone state is collapsed");
  toggle.onclick(); assert.equal(expanded(), "true");
  handlers.pointerdown({ target: mode });
  assert.equal(expanded(), "true", "operating a layer control keeps it open");
  toggle.onclick(); assert.equal(expanded(), "false", "a second tap closes it");
  toggle.onclick();
  handlers.pointerdown({ target: get("map") });
  assert.equal(expanded(), mobile.matches ? "false" : "true");
  if (!mobile.matches) continue;
  toggle.onclick();
  mode.focus();
  handlers.keydown({ key: "Escape" });
  assert.equal(expanded(), "false");
  assert.equal(document.activeElement, toggle);
  toggle.onclick(); mode.focus();
  mobile.matches = false; mobile.change();
  assert.equal(expanded(), "false");
  assert.equal(document.activeElement, mode, "desktop controls keep focus");
  mobile.matches = true; mobile.change();
  assert.equal(expanded(), "false", "returning to a phone collapses the overlay");
  assert.equal(document.activeElement, toggle, "focus leaves the hidden panel");
  mobile.matches = false; mobile.change();
  assert.equal(document.activeElement, mode, "focus leaves the hidden phone toggle");
}
console.log("Offline phone layer disclosure, outside taps, Escape and resize focus passed.");
