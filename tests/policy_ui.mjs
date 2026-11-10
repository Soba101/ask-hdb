// Policy sources render as named links, even if another tool linked the page first.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const source = await readFile(new URL("../src/ask_hdb/api/static/app.js", import.meta.url), "utf8");
const code = source.slice(source.indexOf("function addResult("), source.indexOf("function clearEvidence("));
class Element {
  constructor(tag) { this.tag = tag; this.children = []; }
  set textContent(text) { this.children = [text]; }
  get textContent() { return this.children.map((c) => typeof c === "string" ? c : c.textContent).join(""); }
  get firstChild() { return this.children[0]; }
  append(...nodes) { this.children.push(...nodes); }
  appendChild(node) { this.append(node); }
  querySelectorAll(tag) {
    return this.children.flatMap((c) => typeof c === "string" ? [] : [...(c.tag === tag ? [c] : []), ...c.querySelectorAll(tag)]);
  }
  querySelector(tag) { return this.querySelectorAll(tag)[0]; }
}
const sources = new Element("div"), document = { createElement: (tag) => new Element(tag) };
const { addResult, addSource } = new Function("document", "sources", code + "return { addResult, addSource };")(document, sources);
const url = "https://www.hdb.gov.sg/example", card = new Element("div");
addSource(url, "2026-11-10");
addResult(card, { name: "policy_explain", result: { sources: [{ title: "Housing support", url }],
  summary: "This text must never render", fetched_at: "2099-01-01" } });
assert.equal(sources.querySelectorAll("a").length, 1);
assert.equal(sources.querySelector("a").textContent, "Housing support");
assert.equal(sources.querySelector("a").href, url);
assert.equal(card.children.length, 0, "no raw result or summary panel");
assert.ok(!sources.textContent.includes("This text must never render"));
assert.ok(!sources.textContent.includes("2099"));
addResult(card, { name: "policy_explain", result: { error: "policy pages not built" } });
assert.equal(card.textContent, "policy pages not built");
console.log("ok");
