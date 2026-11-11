// Display conversions and the preference controller, with no browser or network.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { all, get, folder, fire } from "./ui_dom.mjs";
import { viewport } from "./sheet_dom.mjs";
const plain = (text) => String(text).replaceAll("\u00a0", " "); // display output keeps units whole with no-break spaces
const same = (actual, expected, message) => assert.equal(typeof actual === "string" ? plain(actual) : actual, expected, message);
const { convertAreaText, displayAreaUnits } = await import(pathToFileURL(folder + "/area-units.js"));
const { initPreferences } = await import(pathToFileURL(folder + "/preferences.js"));
const { initSheet } = await import(pathToFileURL(folder + "/sheet.js"));
viewport(375); initSheet();
// Preferences rewrite these @media conditions; one sheet that cannot be read must not stop the rest.
const dark = { media: { mediaText: "(min-width: 0px) and (prefers-color-scheme: dark)" } };
const motion = { media: { mediaText: "(prefers-reduced-motion: no-preference)" } };
document.styleSheets = [{ get cssRules() { throw Error("cross-origin"); } }, { cssRules: [dark, motion, {}] }];
const events = [];
Object.assign(window, { addEventListener() {}, dispatchEvent: (event) => events.push(event.type) });

for (const unit of ["sqm", "sq m", "m²", "square metres", "square meters"]) {
  same(convertAreaText("40 " + unit, "sqft"), "431 sq ft / 40 sqm");
}
for (const range of ["93-96", "93 to 96", "93–96", "93‑96"]) {
  same(convertAreaText(range + " sqm", "sqft"), "1,001-1,033 sq ft / 93-96 sqm");
}
for (const price of ["$5,200 per sqm", "$5,200/sqm", "$5,200 psm", "$5,200 per square metres"]) {
  same(convertAreaText(price, "sqft"), "$483 per sq ft / $5,200 per sqm");
}
for (const text of ["431 sq ft", "431 sqft", "$483 psf", "431 sq ft (40 sqm)", "$483 per sq ft ($5,200 per sqm)", "431 sq ft / 40 sqm", "$483 per sq ft / $5,200 per sqm",
  "Plain 40, $5,200 and 2026", "40 sqmish", "140sqm2"]) {
  same(convertAreaText(text, "sqft"), text);
}
same(convertAreaText("40 sqm and $5,200 per sqm", "sqm"), "40 sqm and $5,200 per sqm");
same(convertAreaText("40 sqm; 431 sqft", "sqft"), "431 sq ft / 40 sqm; 431 sqft");
same(convertAreaText("40.5 sqm", "sqft"), "436 sq ft / 40.5 sqm");
same(convertAreaText("1,000 sqm", "sqft"), "10,764 sq ft / 1,000 sqm");

const answer = document.createElement("div"), strong = document.createElement("strong");
strong.textContent = "40 sqm";
const link = document.createElement("a");
link.href = "https://example.test/40sqm"; link.textContent = link.href;
const choice = document.createElement("button"); choice.textContent = "Ask about 40 sqm";
answer.append(strong, link, choice, " <img src=x> $5,200/sqm");
displayAreaUnits(answer, "sqft");
same(strong.textContent, "431 sq ft / 40 sqm");
same(link.textContent, link.href);
same(choice.textContent, "Ask about 40 sqm");
assert.ok(plain(answer.textContent).endsWith("<img src=x> $483 per sq ft / $5,200 per sqm"));
same(all(answer).filter((e) => e.tagName === "img").length, 0);
displayAreaUnits(answer, "sqft");
same(strong.textContent, "431 sq ft / 40 sqm", "no repeated conversions");
displayAreaUnits(answer, "sqm");
same(strong.textContent, "40 sqm");

const source = await readFile(new URL("../src/ask_hdb/api/static/app.js", import.meta.url), "utf8");
const code = source.slice(source.indexOf("function inline("), source.indexOf("function add("));
const render = new Function("document", code + "return render;")(document);
const markdown = document.createElement("div");
render(markdown, "**40 sqm** <img src=x> [93-96 sqm](https://example.test/40sqm)");
displayAreaUnits(markdown, "sqft");
assert.ok(plain(markdown.textContent).includes("431 sq ft / 40 sqm <img src=x> 1,001-1,033 sq ft / 93-96 sqm"));
same(markdown.querySelector("a").href, "https://example.test/40sqm");
same(markdown.querySelector("img"), null);
displayAreaUnits(markdown, "sqm");
same(markdown.querySelector("strong").textContent, "40 sqm");

const button = get("preferences-button"), dialog = get("preferences"), select = get("area-unit");
same(button.tagName, "button");
same(button.getAttribute("aria-label"), "Preferences");
same(button.getAttribute("type"), "button");
assert.ok(all(dialog).some((e) => e.tagName === "label" && e.getAttribute("for") === select.id));
dialog.showModal = () => { dialog.open = true; select.focus(); };
dialog.close = () => { dialog.open = false; fire(dialog, "close"); };
let saved = null;
globalThis.localStorage = {
  getItem(key) { same(key, "ask-hdb.areaUnit"); return saved; },
  setItem(key, value) { same(key, "ask-hdb.areaUnit"); saved = value; },
};
const preferences = initPreferences((unit) => displayAreaUnits(answer, unit));
same(preferences.areaUnit(), "sqm");
fire(button, "click"); assert.ok(dialog.open); same(document.activeElement, select);
same(get("side").dataset.snap, "peek", "opening preferences does not expand the phone chat");
select.value = "sqft"; fire(select, "change");
same(saved, "sqft"); same(strong.textContent, "431 sq ft / 40 sqm");
fire(get("preferences-close"), "click");
same(dialog.open, false); same(document.activeElement, button);
fire(button, "click");
same(fire(dialog, "cancel").defaultPrevented, true, "Escape uses the dialog cancel event");
same(dialog.open, false); same(document.activeElement, button);
same(initPreferences(() => {}).areaUnit(), "sqft", "reload restores the preference");
saved = "unexpected";
same(initPreferences(() => {}).areaUnit(), "sqm");
globalThis.localStorage = {
  getItem() { throw Error("Read blocked"); },
  setItem() { throw Error("Write blocked"); },
};
const throwing = initPreferences(() => {});
same(throwing.areaUnit(), "sqm");
select.value = "sqft"; fire(select, "change");
same(throwing.areaUnit(), "sqft");
Object.defineProperty(globalThis, "localStorage", { configurable: true, get() { throw Error("Storage blocked"); } });
const blocked = initPreferences((unit) => displayAreaUnits(answer, unit));
same(blocked.areaUnit(), "sqm");
select.value = "sqft"; fire(select, "change");
same(blocked.areaUnit(), "sqft");
globalThis.localStorage = { getItem: () => null, setItem() {} };
initPreferences(() => {});
const theme = get("theme"), motionSelect = get("motion");
theme.value = "dark"; fire(theme, "change");
same(dark.media.mediaText, "(min-width: 0px) and (min-width: 0px)", "forced dark turns the dark rules on");
theme.value = "light"; fire(theme, "change");
same(dark.media.mediaText, "(min-width: 0px) and (max-width: 0px) and (min-width: 1px)", "forced light turns them off");
theme.value = "system"; fire(theme, "change");
same(dark.media.mediaText, "(min-width: 0px) and (prefers-color-scheme: dark)", "Match device restores the rule");
motionSelect.value = "reduce"; fire(motionSelect, "change");
same(motion.media.mediaText, "(max-width: 0px) and (min-width: 1px)", "reduced motion turns off the animations");
assert.ok(events.includes("preferences"), "script checks hear the change");
console.log("Area conversion, safe display refresh, preference focus and unavailable storage passed.");

assert.equal(convertAreaText("1,001 sqm", "sqft"), "10,775\u00a0sq\u00a0ft / 1,001\u00a0sqm");
