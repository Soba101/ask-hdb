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
render(div, "### Sales\n* **2026-09**: $858,000\n---\n| Month | Price |\n|---|---|\n| 2026-09 | $858,000 |\n*(Note: MOE measures it.)*");
const [h, li, hr, wrap, note] = div.children;
assert.equal(h.className, "md-h"); assert.equal(h.text, "Sales");
assert.equal(li.className, "md-li"); assert.equal(li.text, "• 2026-09: $858,000");
assert.equal(li.children[1].tag, "strong");
assert.equal(hr.tag, "hr");
const table = wrap.children[0];
assert.equal(table.rows.length, 2); // the |---| line is dropped
assert.equal(table.rows[0].children[0].tag, "th"); assert.equal(table.rows[1].children[1].text, "$858,000");
assert.equal(note.text, "(Note: MOE measures it.)");
assert.equal(div.children.length, 5);
console.log("ok");
