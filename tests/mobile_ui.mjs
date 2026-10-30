// Width boundaries and repeated round trips must preserve nodes, order, ids and handlers.
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { all, get, folder, fire } from "./ui_dom.mjs";
import { viewport, snapshot } from "./sheet_dom.mjs";
const { initSheet } = await import(pathToFileURL(folder + "/sheet.js"));
// One page, one sheet: the same nodes serve every width, so each width below is a re-snap, not a rebuild.
const { wide } = viewport(375);
const form = get("form"), summary = get("card-summary");
let clicks = 0; get("selected-clear").onclick = () => { clicks++; };
const sheet = initSheet();
for (const width of [360, 375, 430, 800, 801, 1280]) {
  wide.matches = width > 800; wide.change();
  assert.equal(get("form").parentNode.id, "topbar", "the search bar is the chat input at every width");
  const hosts = [["form", "topbar"], ["selected", "topbar"], ["toggle-3d", "chips"],
    ["price-controls", "chip-detail"], ["lease-controls", "chip-detail"], ["mop-controls", "chip-detail"], ["sun-panel", "sun-bar"],
    ["building-error", "sheet-notes"], ["sun-panel-limits", "sheet-notes"]];
  for (let round = 0; round < 2; round++) {
    for (const [id, host] of hosts) assert.equal(get(id).parentNode.id, host);
    assert.equal(get("card").parentNode.children[0], get("card"));
    assert.ok(get("sheet-notes").contains(get("layer-note")));
    assert.equal(get("layer-note").parentNode.tagName, "details");
    assert.equal(get("chips").children[0].className, "seg");
    assert.ok(get("sheet-peek").contains(all().find((node) => node.className === "legend")));
    assert.equal(get("form"), form); assert.equal(get("card-summary"), summary);
    assert.equal(get("side").getAttribute("role"), "region");
    fire(get("selected-clear"), "click");
    const ids = all().map((node) => node.id).filter(Boolean);
    assert.equal(new Set(ids).size, ids.length);
    get("flat-type").focus();
    sheet.select({ id: "blk_a" });
    // Crossing the breakpoint re-snaps the sheet; it never moves a node or a handler.
    wide.matches = width <= 800; wide.change();
    assert.equal(document.activeElement, get("flat-type"), "resize preserves control focus");
    for (const [id, host] of hosts) assert.equal(get(id).parentNode.id, host);
    assert.equal(get("side").dataset.snap, wide.matches ? "full" : "half");
    sheet.select(null);
    wide.matches = width > 800; wide.change();
  }
}
assert.equal(clicks, 12, "moved controls retain their original handlers");
console.log("The sheet system at every width passed.");
// iOS phone styling: string-match the key rules, and check every rule sits in a width query: the sheet look for all widths, the docked panel for wide screens.
import { readFileSync } from "node:fs";
const css = readFileSync(folder + "/style.css", "utf8");
const ios = css.slice(css.indexOf("The Apple Maps look"));
for (const rule of ["blur(30px) saturate(180%)", "-webkit-backdrop-filter: blur(30px) saturate(180%)", "border-radius: 12px 12px 0 0",
  "width: 36px; height: 5px", "rgba(118, 118, 128, .12)", "rgba(118, 118, 128, .24)", "#0071e3", "#636366", "#aeaeb2", "clip-path: inset(50%)", "text-overflow: ellipsis", "cubic-bezier(.2, .9, .3, 1.1)",
  "data:image/svg+xml", "border-radius: 50%", "#card-sections { display: flex; flex-direction: column", "min-height: 44px", "width: 22px; height: 22px",
  "height: 4px", "font-size: var(--t-title); font-weight: 700", '"SF Pro Display"', "rgba(255, 255, 255, .9)", "rgba(28, 28, 30, .9)"])
  assert.ok(ios.includes(rule), "missing phone rule: " + rule);
assert.ok(!/font-weight:\s*500/.test(css), "no weight 500");
assert.ok(!ios.includes("gradient"), "no new gradients");
assert.ok(!ios.includes("display: contents") && !/(^|[\s;{])order:\s*\d/.test(ios), "card sections keep real DOM order");
assert.ok(!/#card-\w+ > h3[^}]*display: none/.test(ios), "section headings stay available to screen readers");
// The spring only runs when motion is welcome.
assert.match(ios, /prefers-reduced-motion: no-preference\) \{\s*#side \{ transition: height 420ms cubic-bezier/);
// Every top-level at-rule after the marker is a phone query, so nothing leaks to desktop.
for (const match of ios.matchAll(/^@media ([^{]+)\{/gm)) assert.match(match[1], /max-width: 800px|min-width: 0px|min-width: 801px/);
console.log("iOS phone styling rules passed.");
