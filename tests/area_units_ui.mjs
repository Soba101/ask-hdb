// Display conversions and the preference controller, with no browser or network.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { all, get, folder, fire } from "./ui_dom.mjs";
import { viewport } from "./sheet_dom.mjs";
const { convertAreaText, displayAreaUnits } = await import(pathToFileURL(folder + "/area-units.js"));
const { initPreferences } = await import(pathToFileURL(folder + "/preferences.js"));
const { initSheet } = await import(pathToFileURL(folder + "/sheet.js"));
viewport(375); initSheet();

for (const unit of ["sqm", "sq m", "m²", "square metres", "square meters"]) {
  assert.equal(convertAreaText("40 " + unit, "sqft"), "431 sq ft / 40 sqm");
}
for (const range of ["93-96", "93 to 96", "93–96", "93‑96"]) {
  assert.equal(convertAreaText(range + " sqm", "sqft"), "1,001-1,033 sq ft / 93-96 sqm");
}
for (const price of ["$5,200 per sqm", "$5,200/sqm", "$5,200 psm", "$5,200 per square metres"]) {
  assert.equal(convertAreaText(price, "sqft"), "$483 per sq ft / $5,200 per sqm");
}
for (const text of ["431 sq ft", "431 sqft", "$483 psf", "431 sq ft (40 sqm)", "$483 per sq ft ($5,200 per sqm)", "431 sq ft / 40 sqm", "$483 per sq ft / $5,200 per sqm",
  "Plain 40, $5,200 and 2026", "40 sqmish", "140sqm2"]) {
  assert.equal(convertAreaText(text, "sqft"), text);
}
assert.equal(convertAreaText("40 sqm and $5,200 per sqm", "sqm"), "40 sqm and $5,200 per sqm");
assert.equal(convertAreaText("40 sqm; 431 sqft", "sqft"), "431 sq ft / 40 sqm; 431 sqft");
assert.equal(convertAreaText("40.5 sqm", "sqft"), "436 sq ft / 40.5 sqm");
assert.equal(convertAreaText("1,000 sqm", "sqft"), "10,764 sq ft / 1,000 sqm");

const answer = document.createElement("div"), strong = document.createElement("strong");
strong.textContent = "40 sqm";
const link = document.createElement("a");
link.href = "https://example.test/40sqm"; link.textContent = link.href;
const choice = document.createElement("button"); choice.textContent = "Ask about 40 sqm";
answer.append(strong, link, choice, " <img src=x> $5,200/sqm");
displayAreaUnits(answer, "sqft");
assert.equal(strong.textContent, "431 sq ft / 40 sqm");
assert.equal(link.textContent, link.href);
assert.equal(choice.textContent, "Ask about 40 sqm");
assert.ok(answer.textContent.endsWith("<img src=x> $483 per sq ft / $5,200 per sqm"));
assert.equal(all(answer).filter((e) => e.tagName === "img").length, 0);
displayAreaUnits(answer, "sqft");
assert.equal(strong.textContent, "431 sq ft / 40 sqm", "no repeated conversions");
displayAreaUnits(answer, "sqm");
assert.equal(strong.textContent, "40 sqm");

const source = await readFile(new URL("../src/ask_hdb/api/static/app.js", import.meta.url), "utf8");
const code = source.slice(source.indexOf("function inline("), source.indexOf("function add("));
const render = new Function("document", code + "return render;")(document);
const markdown = document.createElement("div");
render(markdown, "**40 sqm** <img src=x> [93-96 sqm](https://example.test/40sqm)");
displayAreaUnits(markdown, "sqft");
assert.ok(markdown.textContent.includes("431 sq ft / 40 sqm <img src=x> 1,001-1,033 sq ft / 93-96 sqm"));
assert.equal(markdown.querySelector("a").href, "https://example.test/40sqm");
assert.equal(markdown.querySelector("img"), null);
displayAreaUnits(markdown, "sqm");
assert.equal(markdown.querySelector("strong").textContent, "40 sqm");

const button = get("preferences-button"), dialog = get("preferences"), select = get("area-unit");
assert.equal(button.tagName, "button");
assert.equal(button.getAttribute("aria-label"), "Preferences");
assert.equal(button.getAttribute("type"), "button");
assert.ok(all(dialog).some((e) => e.tagName === "label" && e.getAttribute("for") === select.id));
dialog.showModal = () => { dialog.open = true; select.focus(); };
dialog.close = () => { dialog.open = false; fire(dialog, "close"); };
let saved = null;
globalThis.localStorage = {
  getItem(key) { assert.equal(key, "ask-hdb.areaUnit"); return saved; },
  setItem(key, value) { assert.equal(key, "ask-hdb.areaUnit"); saved = value; },
};
const preferences = initPreferences((unit) => displayAreaUnits(answer, unit));
assert.equal(preferences.areaUnit(), "sqm");
fire(button, "click"); assert.ok(dialog.open); assert.equal(document.activeElement, select);
assert.equal(get("side").dataset.snap, "peek", "opening preferences does not expand the phone chat");
select.value = "sqft"; fire(select, "change");
assert.equal(saved, "sqft"); assert.equal(strong.textContent, "431 sq ft / 40 sqm");
fire(get("preferences-close"), "click");
assert.equal(dialog.open, false); assert.equal(document.activeElement, button);
fire(button, "click");
assert.equal(fire(dialog, "cancel").defaultPrevented, true, "Escape uses the dialog cancel event");
assert.equal(dialog.open, false); assert.equal(document.activeElement, button);
assert.equal(initPreferences(() => {}).areaUnit(), "sqft", "reload restores the preference");
saved = "unexpected";
assert.equal(initPreferences(() => {}).areaUnit(), "sqm");
globalThis.localStorage = {
  getItem() { throw Error("Read blocked"); },
  setItem() { throw Error("Write blocked"); },
};
const throwing = initPreferences(() => {});
assert.equal(throwing.areaUnit(), "sqm");
select.value = "sqft"; fire(select, "change");
assert.equal(throwing.areaUnit(), "sqft");
Object.defineProperty(globalThis, "localStorage", { configurable: true, get() { throw Error("Storage blocked"); } });
const blocked = initPreferences((unit) => displayAreaUnits(answer, unit));
assert.equal(blocked.areaUnit(), "sqm");
select.value = "sqft"; fire(select, "change");
assert.equal(blocked.areaUnit(), "sqft");
console.log("Area conversion, safe display refresh, preference focus and unavailable storage passed.");
