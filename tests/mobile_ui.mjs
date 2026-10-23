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
