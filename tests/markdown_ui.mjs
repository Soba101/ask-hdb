// The chat renderer in app.js: Markdown lines become blocks built from text nodes.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const source = await readFile(new URL("../src/ask_hdb/api/static/app.js", import.meta.url), "utf8");
const code = source.slice(source.indexOf("function inline("), source.indexOf("function add("));

class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.className = ""; this.rows = []; }
  append(text) { this.children.push(text); }
  appendChild(child) { this.children.push(child); return child; }
  set textContent(text) { this.children = [text]; }
  insertRow() { const row = new Node("tr"); this.rows.push(row); this.children.push(row); return row; }
  get text() { return this.children.map((c) => (typeof c === "string" ? c : c.text)).join(""); }
}
const document = { createElement: (tag) => new Node(tag) };
const { render } = new Function("document", code + "return { render };")(document);

const div = new Node("div");
render(div, [
  "### **Sales** ###", "* **2026-09**: $858,000", "  - nested under it", "1. first numbered", "---",
  "| Condition | Price |", "|---|---|", "| A \\| B | $858,000 |", "| short |", "| 2026-09 | 7 - 9 |", "*(Note: MOE measures it.)*",
  "| not a table |", "",
].join("\n"));
const [h, list, hr, wrap, note, plain] = div.children;
assert.equal(h.tag, "h4"); assert.equal(h.text, "Sales", "closing hashes and bold stars are dropped");
assert.equal(list.tag, "ul");
const [bullet, nested, numbered] = list.children;
assert.equal(bullet.tag, "li"); assert.equal(bullet.text, "• 2026-09: $858,000"); assert.equal(bullet.children[1].tag, "strong");
assert.equal(bullet.className, "md-d0"); assert.equal(nested.className, "md-d1", "two spaces make one nesting level");
assert.equal(numbered.text, "1. first numbered");
assert.equal(hr.tag, "hr");
const table = wrap.children[0];
assert.equal(table.rows.length, 4, "the |---| line is dropped");
assert.equal(table.rows[0].children[0].tag, "th");
assert.deepEqual(table.rows[1].children.map((c) => c.text), ["A | B", "$858,000"], "an escaped pipe stays in its cell");
assert.deepEqual(table.rows[2].children.map((c) => c.text), ["short", ""], "a short row is padded under its headers");
assert.deepEqual(table.rows[3].children.map((c) => c.text), ["2026\u201109", "7\u20119"], "months and ranges use a hyphen that does not break");
assert.equal(note.text, "(Note: MOE measures it.)");
assert.equal(plain.tag, "p"); assert.equal(plain.text, "| not a table |", "pipes without a |---| line stay text");
assert.equal(div.children.length, 7);
console.log("ok");
