// Width boundaries and repeated round trips must preserve nodes, order, ids and handlers.
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { all, get, folder, fire } from "./ui_dom.mjs";
import { viewport, snapshot } from "./sheet_dom.mjs";
const { initSheet } = await import(pathToFileURL(folder + "/sheet.js"));
for (const width of [360, 375, 430, 800, 801]) {
  const before = snapshot(), { mobile } = viewport(width);
  const form = get("form"), summary = get("card-summary");
  let clicks = 0; get("selected-clear").onclick = () => { clicks++; };
  const sheet = initSheet();
  assert.equal(get("form").parentNode.id, width <= 800 ? "topbar" : "chat");
  if (width > 800) {
    for (const [node, children] of before) assert.ok(node.childNodes.length === children.length && node.childNodes.every((child, i) => child === children[i]), node.id);
    assert.equal(get("side").getAttribute("role"), undefined);
  }
  for (let round = 0; round < 2; round++) {
    mobile.matches = true; mobile.change();
    for (const [id, host] of [["form", "topbar"], ["selected", "topbar"], ["toggle-3d", "chips"],
      ["price-controls", "chip-detail"], ["lease-controls", "chip-detail"], ["sun-panel", "sun-bar"],
      ["building-error", "sheet-notes"], ["sun-panel-limits", "sheet-notes"]]) assert.equal(get(id).parentNode.id, host);
    assert.equal(get("card").parentNode.children[0], get("card"));
    assert.ok(get("sheet-notes").contains(get("layer-note")));
    assert.equal(get("layer-note").parentNode.tagName, "details");
    assert.equal(get("chips").children[0].className, "seg");
    assert.ok(get("sheet-peek").contains(all().find((node) => node.className === "legend")));
    assert.equal(get("form"), form); assert.equal(get("card-summary"), summary);
    fire(get("selected-clear"), "click");
    const ids = all().map((node) => node.id).filter(Boolean);
    assert.equal(new Set(ids).size, ids.length);
    get("flat-type").focus();
    sheet.select({ id: "blk_a" });
    mobile.matches = false; mobile.change();
    assert.equal(document.activeElement, get("flat-type"), "resize preserves control focus");
    for (const [node, children] of before) assert.ok(node.childNodes.length === children.length && node.childNodes.every((child, i) => child === children[i]), node.id);
    assert.equal(get("side").getAttribute("role"), undefined);
    assert.equal(get("app").style.getPropertyValue("--sheet-h"), "");
    sheet.select(null);
  }
  assert.equal(clicks, 2, "moved controls retain their original handlers");
}
console.log("Phone widths and exact desktop restoration passed.");
// iOS phone styling: string-match the key rules, and check they all sit inside the phone query so desktop is unchanged.
import { readFileSync } from "node:fs";
const css = readFileSync(folder + "/style.css", "utf8");
const ios = css.slice(css.indexOf("Phone only: native iOS"));
for (const rule of ["blur(30px) saturate(180%)", "-webkit-backdrop-filter: blur(30px) saturate(180%)", "border-radius: 12px 12px 0 0",
  "width: 36px; height: 5px", "rgba(118, 118, 128, .12)", "rgba(118, 118, 128, .24)", "#007aff", "#0a84ff", "cubic-bezier(.2, .9, .3, 1.1)",
  "data:image/svg+xml", "border-radius: 50%", "#card-sections { display: contents; }", "min-height: 44px", "width: 22px; height: 22px",
  "height: 4px", "font-size: var(--t-title); font-weight: 700", '"SF Pro Display"', "rgba(235, 235, 245, .6)", "rgba(60, 60, 67, .6)"])
  assert.ok(ios.includes(rule), "missing phone rule: " + rule);
assert.ok(!/font-weight:\s*500/.test(css), "no weight 500");
assert.ok(!ios.includes("gradient"), "no new gradients");
// The spring only runs when motion is welcome.
assert.match(ios, /prefers-reduced-motion: no-preference\) \{\s*#side \{ transition: height 420ms cubic-bezier/);
// Every top-level at-rule after the marker is a phone query, so nothing leaks to desktop.
for (const match of ios.matchAll(/^@media ([^{]+)\{/gm)) assert.match(match[1], /max-width: 800px/);
console.log("iOS phone styling rules passed.");
